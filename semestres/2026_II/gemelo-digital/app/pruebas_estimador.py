#!/usr/bin/env python3
"""Prueba del estimador de posición contra un PLC simulado con el programa actual (perfil "cargado").

El simulador reproduce cómo pulsa ese programa: en jog, paquetes de 100 pulsos a 4 kHz (25 ms)
que se repiten mientras se mantiene el pulsador, con una pausa de un ciclo de PLC entre paquetes;
en las secuencias, tramos largos con la cantidad exacta de pulsos. La app lee el PLC cada
~100 ms, como con el cable real. Se compara la posición real con la estimada.

    python3 pruebas_estimador.py
"""
import os
import random
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brazo import PerfilCargado, Transmision  # noqa: E402

TR = Transmision()
XMAX, YMAX = TR.rec_x * TR.ppm, TR.rec_y * TR.ppm


class PLCCargadoSimulado:
    """Estado físico y del PLC, avanzado en un hilo a 2 kHz."""

    def __init__(self, pausa=(0.001, 0.003)):
        self.pausa = pausa
        self.real = {'Z': 0.0, 'X': 10000.0, 'Y': 10000.0}
        self.q = {'Q0.2': 0, 'Q0.3': 0, 'Q0.4': 0, 'Q0.5': 0, 'Q0.6': 0, 'Q0.7': 0}
        self.pto = {0: None, 1: None}        # {'resto': pulsos, 'f': Hz, 'cuenta': n}
        self.jog = None                       # (eje, signo)
        self.manual = True
        self.lock = threading.Lock()
        self.vivo = True
        threading.Thread(target=self._bucle, daemon=True).start()

    def _bucle(self):
        t = time.perf_counter()
        pausa = {0: 0.0, 1: 0.0}
        while self.vivo:
            time.sleep(0.0005)
            ahora = time.perf_counter()
            dt, t = ahora - t, ahora
            with self.lock:
                for idx in (0, 1):
                    p = self.pto[idx]
                    if p:
                        paso = min(p['resto'], p['f'] * dt)
                        p['resto'] -= paso
                        ejes = ['Z'] if idx == 0 else [e for e, k in (('X', 'Q0.5'), ('Y', 'Q0.6')) if self.q[k]]
                        for e in ejes:
                            s = -1 if self.q[{'Z': 'Q0.2', 'X': 'Q0.3', 'Y': 'Q0.4'}[e]] else 1
                            self.real[e] += s * paso
                        if p['resto'] <= 1e-9:
                            self.pto[idx] = None
                            pausa[idx] = random.uniform(*self.pausa)   # un ciclo de PLC
                    elif self.jog and (self.jog[0] == 'Z') == (idx == 0):
                        pausa[idx] -= dt
                        if pausa[idx] <= 0:
                            self.pto[idx] = {'resto': 100, 'f': 4000.0, 'cuenta': 100}
                self.real['X'] = min(XMAX, max(0, self.real['X']))
                self.real['Y'] = min(YMAX, max(0, self.real['Y']))

    def pulsar(self, eje, signo):
        with self.lock:
            q = {'Z': 'Q0.2', 'X': 'Q0.3', 'Y': 'Q0.4'}[eje]
            self.q[q] = 1 if signo < 0 else 0
            self.q['Q0.5'] = int(eje == 'X')
            self.q['Q0.6'] = int(eje == 'Y')
            self.jog = (eje, signo)

    def soltar(self):
        with self.lock:
            self.manual = True
            self.jog = None
            self.pto = {0: None, 1: None}      # el programa corta el paquete al soltar

    def tramo(self, eje, pulsos):
        with self.lock:
            self.manual = False
            q = {'Z': 'Q0.2', 'X': 'Q0.3', 'Y': 'Q0.4'}[eje]
            self.q[q] = 1 if pulsos < 0 else 0
            self.q['Q0.5'] = int(eje == 'X')
            self.q['Q0.6'] = int(eje == 'Y')
            self.pto[0 if eje == 'Z' else 1] = {'resto': abs(pulsos), 'f': 4000.0, 'cuenta': abs(pulsos)}

    def ocupado(self):
        with self.lock:
            return bool(self.pto[0] or self.pto[1])

    # ---- interfaz de ClientePPI
    def leer_varios(self, items):
        time.sleep(0.05)                       # medio viaje por el cable
        with self.lock:
            r = self.real
            i0 = (abs(r['Z']) < 30) | ((r['X'] <= 0) << 1) | ((r['X'] >= XMAX) << 2) | \
                 ((r['Y'] <= 0) << 3) | ((r['Y'] >= YMAX) << 4)
            q0 = (bool(self.pto[0]) << 0) | (bool(self.pto[1]) << 1) | (self.q['Q0.2'] << 2) | \
                 (self.q['Q0.3'] << 3) | (self.q['Q0.4'] << 4) | (self.q['Q0.5'] << 5) | \
                 (self.q['Q0.6'] << 6) | (self.q['Q0.7'] << 7)
            i1 = 0
            if self.jog:
                eje, sg = self.jog
                i1 = 1 << {('Z', 1): 0, ('Z', -1): 1, ('X', 1): 2, ('X', -1): 3, ('Y', 1): 4, ('Y', -1): 5}[(eje, sg)]
            i0 |= (0 if self.jog or self.manual else 1) << 5           # I0.5: automatico en los tramos
            sm = bytearray(20)
            for idx, base in ((0, 0), (1, 10)):
                p = self.pto[idx]
                sm[base] = 0x00 if p else 0x80
                struct.pack_into('>H', sm, base + 2, 250)
                struct.pack_into('>I', sm, base + 6, p['cuenta'] if p else 100)
        time.sleep(0.05)
        out = []
        for area, byte, n in items:
            if area == 'I':
                out.append(bytes([i0, i1]))
            elif area == 'Q':
                out.append(bytes([q0]))
            elif area == 'SM':
                out.append(bytes(sm))
            else:
                out.append(bytes(n) if not (area == 'V' and byte == 200) else b'\x80')   # V200.7 referenciado
        return out


def correr(perfil, plc, segundos):
    fin = time.time() + segundos
    while time.time() < fin:
        perfil.leer()


def autocalibracion():
    """PLC con pausas largas entre paquetes (factor real ~0.80): tras un recorrido completo en jog
    de un final al otro, la app debe ajustar su factor y estimar bien los movimientos siguientes."""
    import brazo
    brazo.CALIBRACION = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_prueba_calibracion.json')
    plc = PLCCargadoSimulado(pausa=(0.004, 0.007))
    perfil = PerfilCargado(plc, TR)
    perfil.leer()
    perfil.est.n = dict(plc.real)
    for signo in (-1, 1):                     # X hasta I0.1 y luego hasta I0.2 (170 mm)
        plc.pulsar('X', signo)
        while not ((signo < 0 and plc.real['X'] <= 0) or (signo > 0 and plc.real['X'] >= XMAX)):
            perfil.leer()
        correr(perfil, plc, 0.3)
        plc.soltar()
        correr(perfil, plc, 0.3)
    factor = perfil.est.duty['X']
    plc.pulsar('X', -1)
    correr(perfil, plc, 3)
    plc.soltar()
    correr(perfil, plc, 0.4)
    err = abs(perfil.est.n['X'] - plc.real['X']) / TR.ppm
    plc.vivo = False
    try:
        os.remove(brazo.CALIBRACION)
    except OSError:
        pass
    print(f'autocalibracion X: factor {factor:.3f} (supuesto {perfil.est.DUTY}); tras 3 s de jog error {err:.2f} mm')
    return err


def main():
    plc = PLCCargadoSimulado()
    perfil = PerfilCargado(plc, TR)
    perfil.leer()
    perfil.est.n = dict(plc.real)              # misma posición de partida
    pruebas = [('jog X adelante 3 s', lambda: plc.pulsar('X', 1), 3),
               ('jog X atras 1.5 s', lambda: plc.pulsar('X', -1), 1.5),
               ('jog Y arriba 2.5 s', lambda: plc.pulsar('Y', 1), 2.5),
               ('jog Y abajo 1 s', lambda: plc.pulsar('Y', -1), 1),
               ('jog base + 2 s', lambda: plc.pulsar('Z', 1), 2),
               ('jog base - 1 s', lambda: plc.pulsar('Z', -1), 1)]
    peor = 0
    for nombre, accion, dur in pruebas:
        accion()
        correr(perfil, plc, dur)
        plc.soltar()
        correr(perfil, plc, 0.4)
        err = {e: perfil.est.n[e] - plc.real[e] for e in 'ZXY'}
        mm = max(abs(err['X']), abs(err['Y'])) / TR.ppm
        peor = max(peor, mm)
        print(f'{nombre:20s} real X {plc.real["X"] / TR.ppm:6.1f} Y {plc.real["Y"] / TR.ppm:6.1f} '
              f'base {plc.real["Z"]:7.0f} p | estimado X {perfil.est.n["X"] / TR.ppm:6.1f} '
              f'Y {perfil.est.n["Y"] / TR.ppm:6.1f} base {perfil.est.n["Z"]:7.0f} p')
    for nombre, eje, pulsos in (('tramo Y +12000', 'Y', 12000), ('tramo X -8000', 'X', -8000), ('tramo base +17000', 'Z', 17000)):
        plc.tramo(eje, pulsos)
        while plc.ocupado():
            perfil.leer()
        correr(perfil, plc, 0.3)
        err = abs(perfil.est.n[eje] - plc.real[eje])
        print(f'{nombre:20s} real {plc.real[eje]:8.0f} p | estimado {perfil.est.n[eje]:8.0f} p | error {err:.0f} p')
        if eje != 'Z':
            peor = max(peor, err / TR.ppm)
    plc.vivo = False
    peor = max(peor, autocalibracion())
    print(f'\nPeor error en X/Y: {peor:.2f} mm')
    if peor > 3:
        raise SystemExit('ERROR: la estimación se aleja más de 3 mm')
    print('Prueba superada')


if __name__ == '__main__':
    main()
