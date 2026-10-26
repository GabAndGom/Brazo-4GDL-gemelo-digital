"""Gemelo digital del brazo XK-JS1-1: lectura del PLC, estimación de la posición y órdenes.

Perfiles (se detectan solos al conectar):
- "gemelo":  programa plc/brazo_gemelo.awl. El PLC cuenta los pulsos de cada eje y acepta
             órdenes de movimiento libre (VB1100..VB1119). Posición exacta.
- "cargado": programa que tenía el PLC el 26/10/2026 (versión del de Miguel con mando por
             VB104). Solo homing, secuencias fijas y paro. La posición se ESTIMA con los
             trenes de pulsos que se leen (SMB66..SMB85) y se corrige en los finales de carrera.
- "monitor": cualquier otro programa: solo se leen entradas/salidas y se estima la posición.
"""
import json
import os
import random
import struct
import threading
import time

from ppi import ClientePPI, ErrorPPI, buscar_plc

APP = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(APP, 'ui')
# Copia local (la deja empaquetar.py); dentro del repositorio se puede usar la original
PARAMETROS = os.path.join(APP, 'parametros.json')
if not os.path.exists(PARAMETROS):
    PARAMETROS = os.path.join(APP, '..', '..', 'modelo-3d', 'cinematica', 'parametros.json')


def bits(byte, prefijo):
    return {f'{prefijo}.{b}': bool((byte >> b) & 1) for b in range(8)}


class Transmision:
    """Conversión mm/grados <-> pulsos, desde parametros.json (fuente: web/js/cinematica.js)."""

    def __init__(self, ruta=PARAMETROS):
        with open(ruta, encoding='utf-8') as f:
            d = json.load(f)
        p, t = d['parametros'], d['transmision']
        self.ppm = t['pulsosPorMm']             # pulsos por mm (X, Y)
        self.ppg = t['pulsosPorGrado']          # pulsos por grado (base, SUPUESTO)
        self.rec_x, self.rec_y = p['recorridoX'], p['recorridoY']
        self.theta_min, self.theta_max = p['thetaMin'], p['thetaMax']

    def a_pulsos(self, theta, sx, sy):
        return round(theta * self.ppg), round(sx * self.ppm), round(sy * self.ppm)

    def de_pulsos(self, nz, nx, ny):
        return nz / self.ppg, nx / self.ppm, ny / self.ppm


# ====================================================================== perfiles
class Perfil:
    nombre = 'monitor'
    zonas = []
    ordenes = []                     # órdenes que acepta, para la interfaz

    def __init__(self, cli, tr):
        self.cli, self.tr = cli, tr
        self.mensaje = ''

    def leer(self):
        raise NotImplementedError

    def latido(self):
        pass

    def orden(self, nombre, datos):
        raise ValueError(f'el programa cargado en el PLC no acepta la orden "{nombre}"')


class Estimador:
    """Estima la posición con los PTO del S7-200 cuando el programa no la cuenta.

    En cada lectura: si un PTO está ocupado se integran f * dt pulsos (f = 1e6 / ciclo) en el
    sentido de su DIR y en los ejes cuyo relé está cerrado (Q0.1 -> K1 X, K2 Y). Al terminar un
    tramo largo se ajusta al número exacto de pulsos del tramo (SMD72 / SMD82). Los finales
    de carrera y el inductivo de la base corrigen la estimación.
    """

    def __init__(self):
        self.n = {'Z': 0.0, 'X': 0.0, 'Y': 0.0}
        self.t = None
        self.tramo = {0: None, 1: None}
        self.prev_i = {}
        self.confiable = False

    def actualizar(self, ent, sal, sm, xmax, ymax):
        ahora = time.time()
        dt = 0 if self.t is None else min(0.5, ahora - self.t)
        self.t = ahora
        ocupado0, ocupado1 = not (sm[0] & 0x80), not (sm[10] & 0x80)
        ciclo0, ciclo1 = struct.unpack('>H', sm[2:4])[0], struct.unpack('>H', sm[12:14])[0]
        cuenta0, cuenta1 = struct.unpack('>I', sm[6:10])[0], struct.unpack('>I', sm[16:20])[0]
        s_z = -1 if sal['Q0.2'] else 1
        s_x = -1 if sal['Q0.3'] else 1
        s_y = -1 if sal['Q0.4'] else 1
        ejes1 = [e for e, k in (('X', 'Q0.5'), ('Y', 'Q0.6')) if sal[k]]

        for idx, ocupado, ciclo, cuenta, ejes, signos in (
                (0, ocupado0, ciclo0, cuenta0, ['Z'], {'Z': s_z}),
                (1, ocupado1, ciclo1, cuenta1, ejes1, {'X': s_x, 'Y': s_y})):
            tr = self.tramo[idx]
            if ocupado:
                f = 1e6 / ciclo if ciclo else 0
                if tr is None:
                    tr = self.tramo[idx] = {'inicio': {e: self.n[e] for e in self.n}, 'cuenta': cuenta,
                                            'ejes': list(ejes), 'signos': dict(signos), 'hecho': 0.0}
                    paso = f * dt / 2       # el tramo empezó, en promedio, a mitad del intervalo
                else:
                    paso = f * dt
                paso = min(paso, max(0.0, tr['cuenta'] - tr['hecho']))
                tr['hecho'] += paso
                for e in ejes:
                    self.n[e] += signos[e] * paso
            elif tr is not None:
                # Tramo terminado. Los paquetes cortos (jog) ya están integrados; en los largos
                # se usa la cuenta exacta si nada lo cortó antes (un final de carrera lo corrige).
                if tr['cuenta'] > 300 and tr['cuenta'] < 400000 and not tr.get('corregido'):
                    for e in tr['ejes']:
                        self.n[e] = tr['inicio'][e] + tr['signos'][e] * tr['cuenta']
                self.tramo[idx] = None

        # Correcciones con los sensores (flanco de subida)
        for k, eje, valor in (('I0.1', 'X', 0), ('I0.2', 'X', xmax), ('I0.3', 'Y', 0), ('I0.4', 'Y', ymax),
                              ('I0.0', 'Z', 0)):
            if ent[k] and not self.prev_i.get(k):
                self.n[eje] = valor
                if self.tramo[1] and eje in ('X', 'Y'):
                    self.tramo[1]['corregido'] = True
                if self.tramo[0] and eje == 'Z':
                    self.tramo[0]['corregido'] = True
        self.prev_i = {k: ent[k] for k in ('I0.0', 'I0.1', 'I0.2', 'I0.3', 'I0.4')}
        return ocupado0 or ocupado1

    def poner_cero(self):
        self.n = {'Z': 0.0, 'X': 0.0, 'Y': 0.0}
        self.tramo = {0: None, 1: None}
        self.confiable = True


class PerfilMonitor(Perfil):
    nombre = 'monitor'
    descripcion = 'Programa desconocido: solo lectura de entradas y salidas, posición estimada'

    def __init__(self, cli, tr):
        super().__init__(cli, tr)
        self.est = Estimador()

    def _leer_es(self):
        ib = self.cli.leer('I', 0, 2)
        qb = self.cli.leer('Q', 0, 1)
        sm = self.cli.leer('SM', 66, 20)
        ent = dict(bits(ib[0], 'I0'), **bits(ib[1], 'I1'))
        sal = bits(qb[0], 'Q0')
        mov = self.est.actualizar(ent, sal, sm, self.tr.rec_x * self.tr.ppm, self.tr.rec_y * self.tr.ppm)
        return ent, sal, sm, mov

    def _estado(self, ent, sal, mov, extra):
        th, sx, sy = self.tr.de_pulsos(self.est.n['Z'], self.est.n['X'], self.est.n['Y'])
        e = {'theta_deg': th, 'sX_mm': sx, 'sY_mm': sy, 'garra': sal['Q0.7'], 'en_movimiento': mov,
             'estimado': True, 'pulsos': {k: round(v) for k, v in self.est.n.items()},
             'entradas': ent, 'salidas': sal, 'modo_auto': ent['I0.5']}
        e.update(extra)
        return e

    def leer(self):
        ent, sal, sm, mov = self._leer_es()
        return self._estado(ent, sal, mov, {'referenciado': self.est.confiable,
                                            'plc': {'programa': 'desconocido'}})


class PerfilCargado(PerfilMonitor):
    """Programa cargado en el PLC al 26/10/2026 (respaldo_vm/programa_plc_cargado_20261026.mwp)."""
    nombre = 'cargado'
    descripcion = 'Programa de secuencias (versión del de Miguel): homing, secuencias 1 y 2, paro'
    zonas = [('V', 100, 100), ('V', 104, 104)]
    ordenes = ['iniciar', 'detener', 'emergencia', 'rearmar']

    def __init__(self, cli, tr):
        super().__init__(cli, tr)
        self.ref_prev = False
        self.hb = False
        self.t_hb = 0

    def leer(self):
        ent, sal, sm, mov = self._leer_es()
        v = self.cli.leer('V', 200, 124)          # VB200..VB323
        b200, b300, b301, b302 = v[0], v[100], v[101], v[102]
        paso_auto, paso_homing = struct.unpack('>HH', v[120:124])
        referenciado = bool(b200 & 0x80)           # V200.7 = M0.3
        if referenciado and not self.ref_prev:
            self.est.poner_cero()                  # el homing terminó: los tres ejes en 0
        if not referenciado:
            self.est.confiable = False
        self.ref_prev = referenciado
        secuencia = 'homing' if b301 & 0x01 else 'secuencia 1' if b301 & 0x04 else \
            'secuencia 2' if b301 & 0x10 else 'reposo'
        siguiente = 'homing' if not referenciado else ('secuencia 2' if b302 & 0x01 else 'secuencia 1')
        return self._estado(ent, sal, bool(mov or paso_auto or paso_homing), {
            'referenciado': referenciado,
            'plc': {'programa': 'secuencias (cargado)', 'listo': bool(b200 & 0x01), 'ocupado': bool(b200 & 0x02),
                    'falla_homing': bool(b200 & 0x08), 'en_curso': secuencia, 'siguiente': siguiente,
                    'paso_auto': paso_auto, 'paso_homing': paso_homing,
                    'remoto': ent['I0.5'], 'VB104': self.cli.leer('V', 104, 1)[0]}})

    def latido(self):
        # V104.7 debe cambiar antes de 5 s; si no, el PLC borra VB104 (las órdenes de la PC)
        if time.time() - self.t_hb > 1.0:
            self.hb = not self.hb
            self.cli.escribir_bit('V', 104, 7, self.hb)
            self.t_hb = time.time()

    def _pulso(self, byte, bit, dur=0.4):
        self.cli.escribir_bit('V', byte, bit, True)
        time.sleep(dur)
        self.cli.escribir_bit('V', byte, bit, False)

    def orden(self, nombre, datos):
        if nombre == 'iniciar':        # como I0.7: homing si no hay referencia; si no, la secuencia siguiente
            self._pulso(104, 0)
        elif nombre == 'detener':      # V104.1: paro en modo automático
            self._pulso(104, 1)
        elif nombre == 'emergencia':   # V104.2: corta todo en cualquier modo, queda enclavado
            self._pulso(104, 2, 0.6)
        elif nombre == 'rearmar':      # V100.3: quita el enclavamiento de emergencia y la falla de homing
            self._pulso(100, 3)
        else:
            super().orden(nombre, datos)
        return {'ok': True}


class PerfilGemelo(Perfil):
    nombre = 'gemelo'
    descripcion = 'Programa del gemelo digital: posición contada en el PLC y movimiento libre'
    zonas = [('V', 1100, 1119)]
    ordenes = ['homing', 'mover', 'detener', 'garra', 'velocidad']
    ERRORES = {0: '', 1: 'orden rechazada: el brazo está ocupado', 2: 'destino fuera del recorrido',
               3: 'watchdog: se perdió la comunicación con la PC', 4: 'falta hacer homing',
               5: 'orden desconocida', 6: 'paro'}

    def __init__(self, cli, tr):
        super().__init__(cli, tr)
        self.ack = 0
        self.hb = 0
        self.t_hb = 0
        self.ciclo_xy = 250                       # us -> 4 kHz = 20 mm/s
        self.ciclo_z = 400
        self.tramo_t0 = {}
        self.ultimo = None

    def leer(self):
        v = self.cli.leer('V', 1120, 40)
        estado, ack, flags, err = v[0], v[1], v[2], v[3]
        nz, nx, ny = struct.unpack('>iii', v[4:16])
        paso = struct.unpack('>H', v[16:18])[0]
        ib0, ib1, qb0 = v[18], v[19], v[20]
        sz, sx, sy = struct.unpack('>iii', v[24:36])
        cxy, cz = struct.unpack('>HH', v[36:40])
        self.ack = ack
        ocupado0, ocupado1 = bool(flags & 0x04), bool(flags & 0x08)
        # Interpolación del tramo en curso (el PLC suma el tramo al terminarlo)
        ahora = time.time()
        pos = {'Z': float(nz), 'X': float(nx), 'Y': float(ny)}
        for clave, ocupado, segs, ciclo in (('0', ocupado0, {'Z': sz}, cz), ('1', ocupado1, {'X': sx, 'Y': sy}, cxy)):
            firma = (tuple(segs.values()), nz, nx, ny)
            if not ocupado:
                self.tramo_t0.pop(clave, None)
                continue
            t0 = self.tramo_t0.setdefault(clave, (firma, ahora))
            if t0[0] != firma:
                t0 = self.tramo_t0[clave] = (firma, ahora)
            largo = max(abs(s) for s in segs.values()) or 1
            fr = min(1.0, (ahora - t0[1]) * 1e6 / max(ciclo, 1) / largo)
            for e, s in segs.items():
                pos[e] += s * fr
        th, x, y = self.tr.de_pulsos(pos['Z'], pos['X'], pos['Y'])
        ent = dict(bits(ib0, 'I0'), **bits(ib1, 'I1'))
        sal = bits(qb0, 'Q0')
        return {'theta_deg': th, 'sX_mm': x, 'sY_mm': y, 'garra': sal['Q0.7'],
                'referenciado': bool(flags & 0x01), 'en_movimiento': bool(estado) or ocupado0 or ocupado1,
                'estimado': False, 'pulsos': {'Z': nz, 'X': nx, 'Y': ny}, 'entradas': ent, 'salidas': sal,
                'modo_auto': bool(flags & 0x02),
                'plc': {'programa': 'gemelo digital', 'estado': ['reposo', 'homing', 'moviendo'][estado] if estado < 3 else estado,
                        'paso': paso, 'error': self.ERRORES.get(err, f'error {err}'), 'incierta': bool(flags & 0x10),
                        'watchdog': bool(flags & 0x20), 'firma': v[21] == 0x47}}

    def latido(self):
        if time.time() - self.t_hb > 0.5:
            self.hb = (self.hb + 1) & 0xFFFF
            self.cli.escribir('V', 1102, struct.pack('>H', self.hb))
            self.t_hb = time.time()

    def _enviar(self, orden, dz=0, dx=0, dy=0):
        seq = (self.ack + 1) & 0xFF
        self.hb = (self.hb + 1) & 0xFFFF
        bloque = struct.pack('>BBHiiiHH', orden, seq, self.hb, dz, dx, dy, self.ciclo_xy, self.ciclo_z)
        self.cli.escribir('V', 1100, bloque)

    def orden(self, nombre, datos, estado=None):
        if nombre == 'homing':
            self._enviar(1)
        elif nombre == 'detener':
            self._enviar(3)
        elif nombre == 'garra':
            self._enviar(4 if datos.get('cerrada') else 5)
        elif nombre == 'velocidad':
            hz = max(500, min(5000, float(datos.get('hz', 4000))))
            self.ciclo_xy = int(round(1e6 / hz))
            self.ciclo_z = max(250, self.ciclo_xy)
        elif nombre == 'mover':
            if estado is None or not estado['referenciado']:
                raise ValueError('falta hacer homing')
            if not estado['modo_auto']:
                raise ValueError('ponga el selector del panel en automático (I0.5) para mandar desde la PC')
            th = min(self.tr.theta_max, max(self.tr.theta_min, float(datos['theta'])))
            sx = min(self.tr.rec_x, max(0.0, float(datos['sX'])))
            sy = min(self.tr.rec_y, max(0.0, float(datos['sY'])))
            nz, nx, ny = self.tr.a_pulsos(th, sx, sy)
            p = estado['pulsos']
            self._enviar(2, nz - p['Z'], nx - p['X'], ny - p['Y'])
        else:
            super().orden(nombre, datos)
        return {'ok': True}


# ====================================================================== simulador (sin PLC)
class PLCSimulado:
    """Imita al PLC con el programa brazo_gemelo.awl, con la misma interfaz que ClientePPI."""

    def __init__(self, tr):
        self.tr = tr
        self.v = bytearray(2048)
        self.real = {'Z': random.randint(-3000, 3000), 'X': random.randint(4000, 30000), 'Y': random.randint(4000, 30000)}
        self.n = {'Z': 0, 'X': 0, 'Y': 0}
        self.ref = False
        self.garra = False
        self.estado = 0
        self.err = 0
        self.ack = 0
        self.pend = {'Z': 0, 'X': 0, 'Y': 0}
        self.fase = None
        self.hb_prev, self.t_hb = 0, time.time()
        self.lock = threading.Lock()
        self.zonas = []
        threading.Thread(target=self._bucle, daemon=True).start()

    def abrir(self):
        pass

    def cerrar(self):
        pass

    def _entradas(self):
        xmax, ymax = self.tr.rec_x * self.tr.ppm, self.tr.rec_y * self.tr.ppm
        r = self.real
        i0 = (abs(r['Z']) < 20) | ((r['X'] <= 0) << 1) | ((r['X'] >= xmax) << 2) | ((r['Y'] <= 0) << 3) | \
             ((r['Y'] >= ymax) << 4) | (1 << 5)
        return i0

    def _bucle(self):
        t = time.time()
        while True:
            time.sleep(0.01)
            ahora = time.time()
            dt, t = ahora - t, ahora
            with self.lock:
                self._paso(dt)

    def _paso(self, dt):
        cxy, cz = struct.unpack('>HH', self.v[1116:1120])
        fxy, fz = 1e6 / max(200, cxy or 250), 1e6 / max(250, cz or 250)
        xmax = self.tr.rec_x * self.tr.ppm
        if self.estado and self.hb_prev == self.v[1102:1104] and time.time() - self.t_hb > 2:
            self._paro(3)
        if self.hb_prev != self.v[1102:1104]:
            self.hb_prev, self.t_hb = bytes(self.v[1102:1104]), time.time()
        if self.fase == 'homing':
            for eje, f in (('Y', fxy), ('X', fxy), ('Z', 2500)):
                if (eje == 'Z' and abs(self.real['Z']) >= 20) or (eje != 'Z' and self.real[eje] > 0):
                    paso = f * dt
                    self.real[eje] = max(0, self.real[eje] - paso) if eje != 'Z' else \
                        self.real['Z'] - min(paso, self.real['Z']) if self.real['Z'] > 0 else self.real['Z'] + paso
                    break
            else:
                self.real['Z'] = 0
                self.n = {'Z': 0, 'X': 0, 'Y': 0}
                self.ref, self.estado, self.fase = True, 0, None
        elif self.fase == 'mover':
            listo = True
            for eje in 'ZXY':
                if self.pend[eje]:
                    listo = False
                    paso = min(abs(self.pend[eje]), (fz if eje == 'Z' else fxy) * dt)
                    s = 1 if self.pend[eje] > 0 else -1
                    self.real[eje] += s * paso
                    self.n[eje] += s * paso
                    self.pend[eje] -= s * paso
                    if abs(self.pend[eje]) < 1e-6:
                        self.pend[eje] = 0
            if listo:
                self.estado, self.fase = 0, None
                self.n = {k: round(v) for k, v in self.n.items()}
        ymax = self.tr.rec_y * self.tr.ppm
        self.real['X'] = min(xmax, max(0, self.real['X']))
        self.real['Y'] = min(ymax, max(0, self.real['Y']))
        # Orden nueva
        if self.v[1101] != self.ack:
            self.ack = self.v[1101]
            orden = self.v[1100]
            dz, dx, dy = struct.unpack('>iii', self.v[1104:1116])
            self.err = 0
            if orden == 3:
                self._paro(6)
            elif self.estado:
                self.err = 1
            elif orden == 4:
                self.garra = True
            elif orden == 5:
                self.garra = False
            elif orden == 1:
                self.estado, self.fase = 1, 'homing'
            elif orden == 2:
                if not self.ref:
                    self.err = 4
                elif not (0 <= self.n['X'] + dx <= xmax and 0 <= self.n['Y'] + dy <= ymax and abs(self.n['Z'] + dz) <= 50000):
                    self.err = 2
                else:
                    self.pend = {'Z': dz, 'X': dx, 'Y': dy}
                    self.estado, self.fase = 2, 'mover'
            else:
                self.err = 5
        # Estado
        mov_xy = self.fase == 'mover' and (self.pend['X'] or self.pend['Y']) or self.fase == 'homing'
        mov_z = self.fase == 'mover' and self.pend['Z']
        flags = self.ref | (1 << 1) | (bool(mov_z) << 2) | (bool(mov_xy) << 3)
        q0 = (bool(mov_z)) | (bool(mov_xy) << 1) | ((self.pend['Z'] < 0) << 2) | ((self.pend['X'] < 0) << 3) | \
             ((self.pend['Y'] < 0 or self.fase == 'homing') << 4) | (bool(self.pend['X']) << 5) | \
             (bool(self.pend['Y']) << 6) | (self.garra << 7)
        struct.pack_into('>BBBBiiiHBBBB', self.v, 1120, self.estado, self.ack, flags, self.err,
                         round(self.n['Z']), round(self.n['X']), round(self.n['Y']), 0,
                         self._entradas(), 0, q0, 0x47)
        struct.pack_into('>iiiHH', self.v, 1144, 0, 0, 0, cxy or 250, cz or 250)

    def _paro(self, err):
        self.pend = {'Z': 0, 'X': 0, 'Y': 0}
        if self.fase:
            self.ref = False
        self.estado, self.fase, self.err = 0, None, err

    def leer(self, area, byte, n):
        with self.lock:
            if area == 'V':
                return bytes(self.v[byte:byte + n])
            return bytes(n)

    def escribir(self, area, byte, datos):
        if not (area == 'V' and 1100 <= byte and byte + len(datos) - 1 <= 1119):
            raise ErrorPPI('escritura fuera de las zonas permitidas')
        with self.lock:
            self.v[byte:byte + len(datos)] = datos

    def escribir_bit(self, area, byte, bit, valor):
        raise ErrorPPI('no usado en el simulador')


# ====================================================================== controlador
class Brazo:
    """Hilo que lee el PLC continuamente y atiende las órdenes de la interfaz."""

    def __init__(self, puerto='/dev/ttyUSB0', direccion=None, simulado=False, registro=None):
        self.puerto, self.direccion, self.simulado = puerto, direccion, simulado
        self.tr = Transmision()
        self.cli = None
        self.perfil = None
        self.estado = None
        self.conectado = False
        self.mando = False
        self.error = ''
        self.lecturas = 0
        self.t_lectura = 0
        self.registro = registro
        self.cola = []
        self.lock = threading.Lock()
        self.vivo = True
        threading.Thread(target=self._bucle, daemon=True).start()

    # -------------------------------------------------------------- conexión
    def _conectar(self):
        if self.simulado:
            self.cli = PLCSimulado(self.tr)
            self.perfil = PerfilGemelo(self.cli, self.tr)
            self.conectado, self.error = True, ''
            self._log('conectado al PLC simulado (perfil gemelo)')
            return
        if self.direccion is None:
            self._log(f'buscando el PLC en {self.puerto}…')
            r = buscar_plc(self.puerto, direcciones=[6, 2, 7] + [d for d in range(1, 32) if d not in (2, 6, 7)])
            if not r:
                raise ErrorPPI(f'no responde ningún PLC en {self.puerto}')
            self.direccion, baudios = r
        else:
            baudios = 19200
        cli = ClientePPI(self.puerto, plc=self.direccion, baudios=baudios)
        cli.abrir()
        # Detección del programa
        perfil = PerfilMonitor
        try:
            if cli.leer('V', 1141, 1)[0] == 0x47:
                perfil = PerfilGemelo
            elif struct.unpack('>ii', cli.leer('V', 340, 8)) == (30000, 25000):
                perfil = PerfilCargado
        except ErrorPPI:
            pass
        cli.zonas = list(perfil.zonas)
        self.cli, self.perfil = cli, perfil(cli, self.tr)
        self.conectado, self.error = True, ''
        self._log(f'conectado: {self.puerto}, PPI {self.direccion}, {baudios} baudios, perfil "{self.perfil.nombre}"')

    def _bucle(self):
        while self.vivo:
            try:
                if not self.conectado:
                    self._conectar()
                e = self.perfil.leer()
                with self.lock:
                    self.estado = e
                    self.lecturas += 1
                    self.t_lectura = time.time()
                if self.mando:
                    self.perfil.latido()
                time.sleep(0.03 if self.simulado else 0.0)
            except (ErrorPPI, OSError) as ex:
                self.error = str(ex)
                if self.conectado:
                    self._log('comunicación perdida: ' + self.error)
                self.conectado = False
                self.mando = False
                if self.cli:
                    self.cli.cerrar()
                time.sleep(2)

    def _log(self, texto):
        linea = time.strftime('%H:%M:%S ') + texto
        print(linea, flush=True)
        if self.registro:
            with open(self.registro, 'a', encoding='utf-8') as f:
                f.write(linea + '\n')

    # -------------------------------------------------------------- interfaz
    def info(self):
        p = self.perfil
        return {'app': 'gemelo-brazo-xk-js1-1', 'version': 1, 'conectado': self.conectado,
                'simulado': self.simulado, 'puerto': self.puerto, 'direccion': self.direccion,
                'perfil': p.nombre if p else None, 'descripcion': getattr(p, 'descripcion', ''),
                'ordenes': p.ordenes if p else [], 'mando': self.mando, 'error': self.error,
                'transmision': {'pulsosPorMm': self.tr.ppm, 'pulsosPorGrado': self.tr.ppg}}

    def leer_estado(self):
        with self.lock:
            e = dict(self.estado) if self.estado else {}
        e.update({'conectado': self.conectado, 'mando': self.mando, 'error': self.error,
                  'perfil': self.perfil.nombre if self.perfil else None,
                  'edad_s': round(time.time() - self.t_lectura, 2) if self.t_lectura else None})
        return e

    def habilitar_mando(self, si):
        if si and not self.conectado:
            raise ValueError('no hay conexión con el PLC')
        if si and not self.perfil.ordenes:
            raise ValueError('el programa del PLC no acepta órdenes desde la PC')
        self.mando = bool(si)
        self._log('mando desde la PC ' + ('HABILITADO' if si else 'deshabilitado'))

    def orden(self, nombre, datos):
        if not self.conectado:
            raise ValueError('no hay conexión con el PLC')
        paro = nombre in ('detener', 'emergencia')
        if not self.mando and not paro:
            raise ValueError('el mando desde la PC está deshabilitado')
        if nombre not in self.perfil.ordenes:
            raise ValueError(f'el programa del PLC no acepta la orden "{nombre}"')
        self._log(f'orden {nombre} {json.dumps(datos) if datos else ""}')
        if isinstance(self.perfil, PerfilGemelo):
            return self.perfil.orden(nombre, datos, self.leer_estado())
        return self.perfil.orden(nombre, datos)
