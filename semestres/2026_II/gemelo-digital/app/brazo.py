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
CALIBRACION = os.path.join(APP, 'calibracion.json')   # lo que se midió en la planta (base, jog)
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
        self.ppg_supuesto = self.ppg
        self.cal = {}
        self.base_calibrada = False
        try:
            with open(CALIBRACION, encoding='utf-8') as f:
                self.cal = json.load(f)
        except (OSError, ValueError):
            pass
        if self.cal.get('pulsosPorGrado'):
            self.ppg = self.cal['pulsosPorGrado']
            self.base_calibrada = True

    def guardar(self, **cambios):
        self.cal.update(cambios)
        self.cal['fecha'] = time.strftime('%Y-%m-%d %H:%M')
        with open(CALIBRACION, 'w', encoding='utf-8') as f:
            json.dump(self.cal, f, indent=2)

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

    En cada lectura, si un PTO está ocupado se suman f * dt pulsos (f = 1e6 / ciclo) en el
    sentido de su DIR y en los ejes que recibe: Q0.0 -> base; Q0.1 -> X si K1 (Q0.5) está
    cerrado e Y si K2 (Q0.6) lo está.
    - Tramos largos (secuencias, homing): no se pasa de los pulsos del tramo (SMD72 / SMD82)
      y al terminar se ajusta al número exacto, salvo que un sensor lo haya cortado antes.
    - Paquetes cortos del jog del panel (100 pulsos, uno tras otro): se integra sin tope,
      porque entre dos lecturas pasan varios paquetes.
    Los finales de carrera y el inductivo de la base corrigen la estimación al activarse.
    """
    CORTO = 300
    # Jog del panel: paquetes de 100 pulsos (25 ms a 4 kHz) y un ciclo de PLC de pausa entre
    # paquetes -> el eje avanza a f * DUTY mientras el pulsador está apretado (SUPUESTO 0.93,
    # se corrige en cada final de carrera)
    DUTY = 0.93
    PULSADORES = {'Z': (('I1.0', 'Q0.2'), ('I1.1', 'Q0.2')), 'X': (('I1.2', 'Q0.3'), ('I1.3', 'Q0.3')),
                  'Y': (('I1.4', 'Q0.4'), ('I1.5', 'Q0.4'))}
    RELE = {'X': 'Q0.5', 'Y': 'Q0.6'}

    LIMITES = {'X': ('I0.1', 'I0.2'), 'Y': ('I0.3', 'I0.4')}   # (final del lado -, final del lado +)

    def __init__(self, tr=None):
        self.tr = tr
        self.n = {'Z': 0.0, 'X': 0.0, 'Y': 0.0}
        self.t = None
        self.tramo = {0: None, 1: None}
        self.prev_i = {}
        self.jog_prev = {'Z': 0.0, 'X': 0.0, 'Y': 0.0}
        self.confiable = False
        cal = tr.cal if tr else {}
        self.duty = {e: cal.get('duty_' + e, self.DUTY) for e in 'ZXY'}
        self.carrera = {'X': None, 'Y': None}     # {'desde': final, 'pulsos': integrado} para autocalibrar

    def _jog(self, ent, sal, sm, dt):
        """Modo manual: avance de cada eje según el pulsador apretado (con su DIR y su relé)."""
        ciclos = {'Z': struct.unpack('>H', sm[2:4])[0], 'X': struct.unpack('>H', sm[12:14])[0]}
        ciclos['Y'] = ciclos['X']
        for eje, ((p_menos, q_dir), (p_mas, _)) in self.PULSADORES.items():
            apretado = ent[p_menos] != ent[p_mas]            # uno solo de los dos
            if eje in self.RELE:
                apretado = apretado and sal[self.RELE[eje]]
            v = 0.0
            if apretado:
                ciclo = ciclos[eje] or 250
                v = (1e6 / ciclo) * self.duty[eje] * (-1 if sal[q_dir] else 1)
                if eje in self.LIMITES:                       # el PLC no avanza contra un final pisado
                    menos, mas = self.LIMITES[eje]
                    if (v > 0 and ent[mas]) or (v < 0 and ent[menos]):
                        v = 0.0
            # regla del trapecio: el pulsador cambió en algún momento entre dos lecturas
            d = (v + self.jog_prev[eje]) / 2 * dt
            self.n[eje] += d
            if self.carrera.get(eje):
                self.carrera[eje]['pulsos'] += d
            self.jog_prev[eje] = v

    def _autocalibrar(self, eje, final, valor):
        """Al llegar en jog de un final de carrera al opuesto, ajusta el factor del jog de ese eje."""
        c = self.carrera.get(eje)
        largo = (self.tr.rec_x if eje == 'X' else self.tr.rec_y) * self.tr.ppm if self.tr else None
        if c and largo and c['desde'] != final and abs(c['pulsos']) > 0.5 * largo:
            nuevo = min(1.1, max(0.6, self.duty[eje] * largo / abs(c['pulsos'])))
            self.duty[eje] = nuevo
            if self.tr:
                self.tr.guardar(**{'duty_' + eje: round(nuevo, 4)})
        self.carrera[eje] = {'desde': final, 'pulsos': 0.0}

    def _cerrar(self, idx):
        tr = self.tramo[idx]
        if tr and tr['cuenta'] > self.CORTO and not tr.get('corregido') and tr['cuenta'] < 400000:
            for e in tr['ejes']:
                self.n[e] = tr['inicio'][e] + tr['signos'][e] * tr['cuenta']
        self.tramo[idx] = None

    def actualizar(self, ent, sal, sm, xmax, ymax):
        ahora = time.time()
        dt = 0.0 if self.t is None else min(0.6, ahora - self.t)
        self.t = ahora
        datos = {
            0: (not (sm[0] & 0x80), struct.unpack('>H', sm[2:4])[0], struct.unpack('>I', sm[6:10])[0],
                ['Z'], {'Z': -1 if sal['Q0.2'] else 1}),
            1: (not (sm[10] & 0x80), struct.unpack('>H', sm[12:14])[0], struct.unpack('>I', sm[16:20])[0],
                [e for e, k in (('X', 'Q0.5'), ('Y', 'Q0.6')) if sal[k]],
                {'X': -1 if sal['Q0.3'] else 1, 'Y': -1 if sal['Q0.4'] else 1}),
        }
        manual = not ent['I0.5']
        if not manual:
            self.carrera = {'X': None, 'Y': None}
        if manual:
            self._jog(ent, sal, sm, dt)
            self.tramo = {0: None, 1: None}
        else:
            self.jog_prev = {'Z': 0.0, 'X': 0.0, 'Y': 0.0}
        for idx, (ocupado, ciclo, cuenta, ejes, signos) in (() if manual else datos.items()):
            tr = self.tramo[idx]
            firma = (cuenta, tuple(ejes), tuple(signos[e] for e in ejes))
            if tr and (not ocupado or tr['firma'] != firma):
                self._cerrar(idx)                     # terminó, o empezó otro tramo distinto
                tr = None
            if not ocupado or not ejes:
                continue
            f = 1e6 / ciclo if ciclo else 0.0
            if tr is None:
                tr = self.tramo[idx] = {'inicio': dict(self.n), 'cuenta': cuenta, 'ejes': ejes,
                                        'signos': signos, 'hecho': 0.0, 'firma': firma}
                paso = f * dt / 2                     # en promedio empezó a mitad del intervalo
            else:
                paso = f * dt
            if cuenta > self.CORTO:
                paso = min(paso, max(0.0, cuenta - tr['hecho']))
            tr['hecho'] += paso
            for e in ejes:
                self.n[e] += signos[e] * paso

        # Correcciones con los sensores (al activarse)
        for k, eje, valor in (('I0.1', 'X', 0), ('I0.2', 'X', xmax), ('I0.3', 'Y', 0), ('I0.4', 'Y', ymax),
                              ('I0.0', 'Z', 0)):
            if ent[k] and not self.prev_i.get(k):
                if eje in self.LIMITES and not ent['I0.5']:
                    self._autocalibrar(eje, k, valor)
                elif eje in self.LIMITES:
                    self.carrera[eje] = None             # en automático no se calibra el jog
                self.n[eje] = valor
                for idx in (0, 1):
                    if self.tramo[idx] and eje in self.tramo[idx]['ejes']:
                        self.tramo[idx]['corregido'] = True
        self.prev_i = {k: ent[k] for k in ('I0.0', 'I0.1', 'I0.2', 'I0.3', 'I0.4')}
        # Los carros no salen de su recorrido
        self.n['X'] = min(xmax, max(0.0, self.n['X']))
        self.n['Y'] = min(ymax, max(0.0, self.n['Y']))
        return datos[0][0] or datos[1][0]

    def poner_cero(self):
        self.n = {'Z': 0.0, 'X': 0.0, 'Y': 0.0}
        self.tramo = {0: None, 1: None}
        self.confiable = True


class PerfilMonitor(Perfil):
    nombre = 'monitor'
    descripcion = 'Programa desconocido: solo lectura de entradas y salidas, posición estimada'

    def __init__(self, cli, tr):
        super().__init__(cli, tr)
        self.est = Estimador(tr)

    EXTRA = []                       # zonas V adicionales de cada perfil

    def _leer_es(self):
        r = self.cli.leer_varios([('I', 0, 2), ('Q', 0, 1), ('SM', 66, 20)] + self.EXTRA)
        ib, qb, sm = r[0], r[1], r[2]
        self.extra = r[3:]
        ent = dict(bits(ib[0], 'I0'), **bits(ib[1], 'I1'))
        sal = bits(qb[0], 'Q0')
        mov = self.est.actualizar(ent, sal, sm, self.tr.rec_x * self.tr.ppm, self.tr.rec_y * self.tr.ppm)
        # Q0.0 y Q0.1 son salidas de pulsos: la imagen de salidas no las marca, se usan los PTO
        sal['Q0.0'] = not (sm[0] & 0x80)
        sal['Q0.1'] = not (sm[10] & 0x80)
        return ent, sal, sm, mov

    def _estado(self, ent, sal, mov, extra):
        th, sx, sy = self.tr.de_pulsos(self.est.n['Z'], self.est.n['X'], self.est.n['Y'])
        e = {'theta_deg': th, 'sX_mm': sx, 'sY_mm': sy, 'garra': sal['Q0.7'], 'en_movimiento': mov,
             'estimado': True, 'base_calibrada': self.tr.base_calibrada,
             'factor_jog': {k: round(v, 3) for k, v in self.est.duty.items()}, 'pulsos': {k: round(v) for k, v in self.est.n.items()},
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
    ordenes = ['homing', 'iniciar', 'garra', 'detener', 'emergencia', 'rearmar']

    def __init__(self, cli, tr):
        super().__init__(cli, tr)
        self.ref_prev = False
        self.hb = False
        self.t_hb = 0

    EXTRA = [('V', 200, 1), ('V', 300, 3), ('V', 320, 4)]

    def leer(self):
        ent, sal, sm, mov = self._leer_es()
        (b200,), (b300, b301, b302), v320 = self.extra
        paso_auto, paso_homing = struct.unpack('>HH', v320)
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
                    'remoto': ent['I0.5']}})

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

    AVISO_MANUAL = ('el selector del panel está en MANUAL (I0.5 = 0): póngalo en AUTOMÁTICO. '
                    'En manual el PLC usa la orden de inicio solo para abrir o cerrar la garra')

    def orden(self, nombre, datos, estado=None):
        e = estado or {}
        auto = bool(e.get('entradas', {}).get('I0.5'))
        plc = e.get('plc', {})
        if nombre in ('iniciar', 'homing') and not auto:
            raise ValueError(self.AVISO_MANUAL)
        if nombre == 'iniciar':        # como I0.7: homing si no hay referencia; si no, la secuencia siguiente
            self._pulso(104, 0)
        elif nombre == 'homing':
            if e.get('en_movimiento'):
                raise ValueError('espere a que el brazo termine el movimiento en curso')
            if e.get('referenciado'):
                # El programa solo hace homing sin referencia: la emergencia (V104.2) la borra y
                # Rearmar (V100.3) quita el enclavamiento; luego el inicio arranca el homing.
                self._pulso(104, 2, 0.5)
                time.sleep(0.3)
                self._pulso(100, 3)
                time.sleep(0.3)
            if plc.get('falla_homing'):
                self._pulso(104, 1)    # el paro en automático borra la falla de homing (M5.2)
                time.sleep(0.3)
            self._pulso(104, 0)
        elif nombre == 'garra':        # en manual, el inicio (como I0.7) abre o cierra la garra
            if auto:
                raise ValueError('en automático la garra la mueve la secuencia; ponga el selector en manual')
            if bool(datos.get('cerrada')) != bool(e.get('garra')):
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
            self.ciclo_z = max(400, self.ciclo_xy)      # la base, más lenta: arranca sin rampa
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
        self.mando_de = None
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
                self.mando_de = None
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
                'transmision': {'pulsosPorMm': self.tr.ppm, 'pulsosPorGrado': self.tr.ppg,
                                'base_calibrada': self.tr.base_calibrada}}

    def leer_estado(self):
        with self.lock:
            e = dict(self.estado) if self.estado else {}
        e.update({'conectado': self.conectado, 'mando': self.mando, 'mando_de': self.mando_de, 'error': self.error,
                  'perfil': self.perfil.nombre if self.perfil else None,
                  'edad_s': round(time.time() - self.t_lectura, 2) if self.t_lectura else None})
        return e

    def calibrar_base(self, angulo):
        """Con la base girada desde el inductivo (theta = 0) hasta un ángulo medido a mano."""
        angulo = float(angulo)
        if abs(angulo) < 10:
            raise ValueError('gire la base al menos 10° desde el sensor inductivo para calibrar')
        e = self.leer_estado()
        if not e.get('conectado'):
            raise ValueError('no hay conexión con el PLC')
        n = e['pulsos']['Z']
        if abs(n) < 50:
            raise ValueError('la base no se movió desde el sensor inductivo (I0.0)')
        ppg = n / angulo            # con signo: si la base gira al revés de lo supuesto, queda negativo
        self.tr.ppg = ppg
        self.tr.base_calibrada = True
        self.tr.guardar(pulsosPorGrado=ppg)
        self._log(f'base calibrada: {n} pulsos = {angulo}° -> {ppg:.3f} pulsos/° '
                  f'(supuesto anterior {self.tr.ppg_supuesto:.3f}); reducción ≈ {abs(ppg) * 360 / 1000:.1f}:1')
        return {'ok': True, 'pulsosPorGrado': ppg, 'reduccion': abs(ppg) * 360 / 1000}

    def habilitar_mando(self, si, quien='local'):
        """Un solo operador tiene el mando a la vez; lo suelta él (o la PC del laboratorio)."""
        with self.lock:
            if si:
                if not self.conectado:
                    raise ValueError('no hay conexión con el PLC')
                if not self.perfil.ordenes:
                    raise ValueError('el programa del PLC no acepta órdenes desde la PC')
                if self.mando and self.mando_de not in (None, quien):
                    raise ValueError(f'el mando lo tiene {self.mando_de}: pídale que lo suelte')
                self.mando, self.mando_de = True, quien
            else:
                if self.mando and self.mando_de not in (None, quien) and quien != 'local':
                    raise ValueError(f'el mando lo tiene {self.mando_de}')
                self.mando, self.mando_de = False, None
        self._log(f'mando desde la PC {"HABILITADO" if si else "deshabilitado"} ({quien})')

    def soltar_mando_de(self, quien):
        if self.mando and self.mando_de == quien:
            self.habilitar_mando(False, quien)

    def orden(self, nombre, datos, quien='local'):
        if not self.conectado:
            raise ValueError('no hay conexión con el PLC')
        paro = nombre in ('detener', 'emergencia')
        if not paro and not self.mando:
            raise ValueError('el mando desde la PC está deshabilitado: marque "Habilitar el mando" en la pestaña Conexión')
        if not paro and self.mando_de != quien:
            raise ValueError(f'el mando lo tiene {self.mando_de}; usted solo puede dar paro')
        if nombre not in self.perfil.ordenes:
            raise ValueError(f'el programa del PLC no acepta la orden "{nombre}"')
        self._log(f'orden {nombre} {json.dumps(datos) if datos else ""} ({quien})')
        if isinstance(self.perfil, (PerfilGemelo, PerfilCargado)):
            return self.perfil.orden(nombre, datos, self.leer_estado())
        return self.perfil.orden(nombre, datos)
