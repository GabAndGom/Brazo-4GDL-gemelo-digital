#!/usr/bin/env python3
"""Genera la versión 2.0 (Kaizen) de los planos del brazo XK-JS1-1 en DXF, sin dependencias.

    python3 generar_planos_v2.py         -> pid/brazo_pid_v2.dxf y electrico/brazo_electrico_v2.dxf

Luego se convierten a DWG (AutoCAD 2018) con ODA File Converter y a PDF con LibreCAD
(ver README.md). Corrige las discrepancias del plano histórico (laboratorio 1 y 2) con el
cableado verificado en la planta el 26/10/2026 y agrega los tags ISA-5.1 de los lazos 100 a 104.

Normas: P&ID según ANSI/ISA-5.1-2009 (señal eléctrica en trazo discontinuo de 0,25 mm, enlace
de datos con círculos, función de PLC = rombo en cuadrado, pantalla compartida = círculo en
cuadrado, instrumento en campo = círculo, en panel = círculo con línea); esquema eléctrico según
IEC 60617 (designaciones -Q, -G, -K, -S, -B, -M, -Y, -A) e IEC 60204-1.
"""
import math
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
FECHA = '10-11-2026'
EQUIPO = ['Gabriel Andres Gomez Calla', 'Jose Lenin Mamani Choque', 'Miguel Alejandro Lima Huarachi',
          'Román Abner Machicado Arequipa']

# capas: nombre -> (color ACI, tipo de línea)
CAPAS = {
    'MARCO': (7, 'CONTINUOUS'), 'CAJETIN': (7, 'CONTINUOUS'), 'TEXTO': (7, 'CONTINUOUS'),
    'PROCESO': (7, 'CONTINUOUS'),          # P&ID: enlace mecánico (1,0 mm)
    'SENAL': (5, 'DASHED'),                # P&ID: señal eléctrica (0,25 mm)
    'DATOS': (4, 'CONTINUOUS'),            # P&ID: enlace de datos / software
    'INSTRUMENTOS': (2, 'CONTINUOUS'), 'TAGS': (2, 'CONTINUOUS'),
    'POTENCIA': (1, 'CONTINUOUS'), 'CC24': (1, 'CONTINUOUS'), 'CC0V': (5, 'CONTINUOUS'),
    'CC5': (6, 'CONTINUOUS'), 'MANDO': (3, 'CONTINUOUS'), 'SIMBOLOS': (7, 'CONTINUOUS'),
    'BORNES': (8, 'CONTINUOUS'), 'NUMEROS_CABLE': (3, 'CONTINUOUS'), 'REFERENCIAS': (6, 'CONTINUOUS'),
    'NOTAS': (7, 'CONTINUOUS'), 'REVISION': (1, 'CONTINUOUS'),
}


class DXF:
    """Escritor DXF R12 (AC1009): LINE, CIRCLE, ARC, TEXT, POLYLINE con ancho y SOLID."""

    def __init__(self):
        self.e = []
        self.dx = 0.0                     # desplazamiento de la hoja actual

    def _g(self, *pares):
        self.e.append('\n'.join(f'{c}\n{v}' for c, v in pares))

    def linea(self, x1, y1, x2, y2, capa='SIMBOLOS'):
        self._g((0, 'LINE'), (8, capa), (10, x1 + self.dx), (20, y1), (11, x2 + self.dx), (21, y2))

    def poli(self, pts, capa='SIMBOLOS', ancho=0.0, cerrada=False):
        self._g((0, 'POLYLINE'), (8, capa), (66, 1), (10, 0), (20, 0), (70, 1 if cerrada else 0),
                (40, ancho), (41, ancho))
        for x, y in pts:
            self._g((0, 'VERTEX'), (8, capa), (10, x + self.dx), (20, y), (40, ancho), (41, ancho))
        self._g((0, 'SEQEND'), (8, capa))

    def rect(self, x1, y1, x2, y2, capa='SIMBOLOS', ancho=0.0):
        self.poli([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], capa, ancho, True)

    def circulo(self, x, y, r, capa='SIMBOLOS'):
        self._g((0, 'CIRCLE'), (8, capa), (10, x + self.dx), (20, y), (40, r))

    def arco(self, x, y, r, a1, a2, capa='SIMBOLOS'):
        self._g((0, 'ARC'), (8, capa), (10, x + self.dx), (20, y), (40, r), (50, a1), (51, a2))

    def punto(self, x, y, capa='SIMBOLOS', r=0.6):
        x += self.dx
        self._g((0, 'SOLID'), (8, capa), (10, x - r), (20, y - r), (11, x + r), (21, y - r),
                (12, x - r), (22, y + r), (13, x + r), (23, y + r))

    def texto(self, x, y, t, h=2.5, capa='TEXTO', alin='izq', rot=0):
        """alin: izq, centro, der; con 'm' al final, centrado en vertical."""
        h_al = {'izq': 0, 'centro': 1, 'der': 2}[alin.rstrip('m')]
        v_al = 2 if alin.endswith('m') else 0
        pares = [(0, 'TEXT'), (8, capa), (10, x + self.dx), (20, y), (40, h), (1, t), (7, 'NORMAL')]
        if rot:
            pares.append((50, rot))
        if h_al or v_al:
            pares += [(72, h_al), (11, x + self.dx), (21, y), (73, v_al)]
        self._g(*pares)

    def guardar(self, ruta):
        tabla_ltype = ('0\nTABLE\n2\nLTYPE\n70\n2\n'
                       '0\nLTYPE\n2\nCONTINUOUS\n70\n0\n3\nSolida\n72\n65\n73\n0\n40\n0.0\n'
                       '0\nLTYPE\n2\nDASHED\n70\n0\n3\n__ __ __\n72\n65\n73\n2\n40\n4.5\n49\n3.0\n49\n-1.5\n'
                       '0\nENDTAB\n')
        capas = ''.join(f'0\nLAYER\n2\n{n}\n70\n0\n62\n{c}\n6\n{t}\n' for n, (c, t) in CAPAS.items())
        tabla_layer = f'0\nTABLE\n2\nLAYER\n70\n{len(CAPAS)}\n{capas}0\nENDTAB\n'
        tabla_style = ('0\nTABLE\n2\nSTYLE\n70\n1\n0\nSTYLE\n2\nNORMAL\n70\n0\n40\n0.0\n41\n0.9\n50\n0.0\n'
                       '71\n0\n42\n2.5\n3\narial.ttf\n4\n\n0\nENDTAB\n')
        cab = ('0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1009\n9\n$DWGCODEPAGE\n3\nANSI_1252\n'
               '9\n$INSUNITS\n70\n4\n9\n$LTSCALE\n40\n1.0\n0\nENDSEC\n')
        cuerpo = (cab + '0\nSECTION\n2\nTABLES\n' + tabla_ltype + tabla_layer + tabla_style + '0\nENDSEC\n'
                  + '0\nSECTION\n2\nENTITIES\n' + '\n'.join(self.e) + '\n0\nENDSEC\n0\nEOF\n')
        with open(ruta, 'w', encoding='cp1252', errors='replace', newline='\r\n') as f:
            f.write(cuerpo)


# ====================================================================== marco y cajetín A3
ANCHO, ALTO = 420, 297


def marco(d, titulo, numero, hoja, revisiones, norma):
    d.rect(0, 0, ANCHO, ALTO, 'MARCO')
    d.rect(10, 10, ANCHO - 10, ALTO - 10, 'MARCO', 0.5)
    for i in range(8):                                   # columnas 1..8 y filas A..F (referencias cruzadas)
        x = 10 + i * 50
        d.linea(x, ALTO - 10, x, ALTO - 5, 'MARCO')
        d.linea(x, 10, x, 5, 'MARCO')
        d.texto(x + 25, ALTO - 7.5, str(i + 1), 2.5, 'MARCO', 'centrom')
        d.texto(x + 25, 7.5, str(i + 1), 2.5, 'MARCO', 'centrom')
    for j, letra in enumerate('ABCDEF'):
        y = ALTO - 10 - j * 46.17
        d.linea(5, y, 10, y, 'MARCO')
        d.linea(ANCHO - 10, y, ANCHO - 5, y, 'MARCO')
        d.texto(7.5, y - 23, letra, 2.5, 'MARCO', 'centrom')
        d.texto(ANCHO - 7.5, y - 23, letra, 2.5, 'MARCO', 'centrom')
    # cajetín (180 x 62 mm, abajo a la derecha)
    x0, y0, x1, y1 = ANCHO - 190, 10, ANCHO - 10, 72
    d.rect(x0, y0, x1, y1, 'CAJETIN', 0.5)
    for y in (62, 50, 38, 26, 18):
        d.linea(x0, y, x1, y, 'CAJETIN')
    d.linea(x0 + 120, 10, x0 + 120, 38, 'CAJETIN')
    d.linea(x0 + 60, 10, x0 + 60, 26, 'CAJETIN')
    d.texto(x0 + 90, 67, 'UNIVERSIDAD MAYOR DE SAN ANDRÉS · FACULTAD DE INGENIERÍA', 2.5, 'CAJETIN', 'centrom')
    d.texto(x0 + 90, 56, 'Laboratorio de Control de Procesos · ETN-902 / ETN-1034 / ETN-1000', 2.2, 'CAJETIN', 'centrom')
    d.texto(x0 + 90, 44, titulo, 3.5, 'CAJETIN', 'centrom')
    d.texto(x0 + 2, 34, 'Proyecto:', 1.8, 'CAJETIN')
    d.texto(x0 + 2, 29.5, 'Brazo robótico XK-JS1-1 (4 GDL) · gemelo digital', 2.2, 'CAJETIN')
    d.texto(x0 + 122, 34, 'Plano N°', 1.8, 'CAJETIN')
    d.texto(x0 + 150, 29.5, numero, 2.6, 'CAJETIN', 'centro')
    d.texto(x0 + 2, 22.5, 'Revisión: 2.0 (Kaizen)', 2.0, 'CAJETIN')
    d.texto(x0 + 62, 22.5, f'Fecha: {FECHA}', 2.0, 'CAJETIN')
    d.texto(x0 + 122, 22.5, f'Hoja {hoja}', 2.0, 'CAJETIN')
    d.texto(x0 + 2, 14, 'Dibujó: ' + EQUIPO[0], 1.8, 'CAJETIN')
    d.texto(x0 + 2, 11.2, ' / '.join(EQUIPO[1:3]), 1.4, 'CAJETIN')
    d.texto(x0 + 62, 14, 'Revisó: Ing. Jorge A. Nava A.', 1.8, 'CAJETIN')
    d.texto(x0 + 62, 11.2, 'Emitido para revisión', 1.6, 'CAJETIN')
    d.texto(x0 + 122, 14, f'Norma: {norma}', 1.8, 'CAJETIN')
    d.texto(x0 + 122, 11.2, 'Escala: sin escala · A3', 1.6, 'CAJETIN')
    # tabla de revisiones sobre el cajetín
    ry = 72
    d.rect(x0, ry, x1, ry + 6 + 4.2 * len(revisiones), 'REVISION')
    d.texto(x0 + 2, ry + 2.2 + 4.2 * len(revisiones), 'REV. 2.0 · CAMBIOS RESPECTO DEL PLANO HISTÓRICO (Kaizen)', 2.0, 'REVISION')
    for i, r in enumerate(revisiones):
        d.texto(x0 + 2, ry + 1.6 + 4.2 * (len(revisiones) - 1 - i), f'{i + 1}. {r}', 1.7, 'REVISION')
    return ry + 6 + 4.2 * len(revisiones)


# ====================================================================== símbolos ISA-5.1
R = 6.0     # radio de los globos de instrumentos


def globo(d, x, y, letras, numero, lugar='campo'):
    """lugar: campo (círculo), panel (círculo con línea), plc (rombo en cuadrado), hmi (círculo en cuadrado)."""
    if lugar in ('plc', 'hmi'):
        d.rect(x - R, y - R, x + R, y + R, 'INSTRUMENTOS')
    if lugar == 'plc':
        d.poli([(x - R, y), (x, y + R), (x + R, y), (x, y - R)], 'INSTRUMENTOS', cerrada=True)
    else:
        d.circulo(x, y, R, 'INSTRUMENTOS')
    if lugar in ('panel', 'hmi'):
        d.linea(x - R, y, x + R, y, 'INSTRUMENTOS')
    d.texto(x, y + 1.0, letras, 2.2, 'TAGS', 'centro')
    d.texto(x, y - 3.2, numero, 2.2, 'TAGS', 'centro')


def senal(d, pts):
    d.poli(pts, 'SENAL')


def enlace_datos(d, x1, y1, x2, y2):
    d.linea(x1, y1, x2, y2, 'DATOS')
    largo = math.hypot(x2 - x1, y2 - y1)
    n = int(largo // 8)
    for i in range(1, n):
        t = i / n
        d.circulo(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, 0.8, 'DATOS')


def pid():
    d = DXF()
    revisiones = [
        'Finales de carrera ZSL/ZSH-102 y -103 en I0.1-I0.4; ZS-101 (inductivo) en I0.0.',
        'Tren de pulsos ZY-100 (Q0.1) compartido por K1/K2 hacia los drivers de X e Y.',
        'Lazos numerados 100 a 104 con tags ISA-5.1 (posición: letra Z).',
        'Garra: XY-104 (Q0.7) por el relé K3 al solenoide XV-104.',
        'Enlace de datos PPI (RS-485) del PLC al gemelo digital ZI-100 en la PC.',
        'Sin realimentación continua: lazo abierto con supervisión discreta (sin encoders).',
    ]
    marco(d, 'DIAGRAMA P&ID DEL BRAZO 4 GDL', 'P&ID-B4G-01', '1 de 1', revisiones, 'ISA-5.1-2009')
    col = {101: 58, 102: 105, 103: 160, 104: 210}
    xpto = 137                                     # función ZY-100 dentro del PLC

    # ---- equipo (proceso mecánico): el brazo
    d.rect(20, 22, 222, 50, 'PROCESO', 1.0)
    d.texto(121, 44, 'BRAZO ROBÓTICO XK-JS1-1 (4 GDL)', 3.0, 'TEXTO', 'centro')
    for (a, b), t in zip(((20, 84), (84, 140), (140, 196), (196, 222)),
                         ('BASE (giro)', 'CARRO X (alcance)', 'CARRO Y (altura)', 'GARRA')):
        d.texto((a + b) / 2, 29, t, 2.2, 'TEXTO', 'centro')
    for x in (84, 140, 196):
        d.linea(x, 22, x, 39, 'PROCESO')

    # ---- gemelo digital (pantalla compartida) y enlace PPI
    globo(d, xpto, 268, 'ZI', '100', 'hmi')
    d.texto(xpto + 9, 269, 'Gemelo digital (app en la PC)', 2.0, 'TEXTO')
    d.texto(xpto + 9, 265.5, 'posición, E/S y mando remoto', 1.7, 'TEXTO')
    enlace_datos(d, xpto, 262, xpto, 206)
    d.texto(xpto - 2, 252, 'PPI · RS-485 · puerto 0', 1.8, 'TEXTO', 'der')
    d.texto(xpto - 2, 248.5, '9600 bit/s · dirección 2', 1.6, 'TEXTO', 'der')

    # ---- PLC (funciones compartidas)
    d.rect(36, 176, 222, 206, 'NOTAS')
    d.texto(38, 202.5, 'PLC S7-200 CPU 224 CN (AT1) · funciones compartidas', 2.0, 'NOTAS')
    globo(d, xpto, 190, 'ZY', '100', 'plc'); d.texto(xpto, 181, 'PTO Q0.1', 1.5, 'TEXTO', 'centro')

    # ---- lazo 100: selector y paro en el panel
    globo(d, 20, 232, 'HS', '100', 'panel'); d.texto(20, 222.5, 'Selector man/auto', 1.5, 'TEXTO', 'centro'); d.texto(20, 220, 'I0.5', 1.5, 'TEXTO', 'centro')
    globo(d, 20, 254, 'HS', '100P', 'panel'); d.texto(20, 244.5, 'Paro (Reset) I0.6', 1.5, 'TEXTO', 'centro')
    senal(d, [(26, 254), (30, 254), (30, 196), (36, 196)])
    senal(d, [(26, 232), (28, 232), (28, 192), (36, 192)])

    tags_plc = {101: ('ZIC', 'Posición base'), 102: ('ZIC', 'Posición X'), 103: ('ZIC', 'Posición Y'), 104: ('XC', 'Garra')}
    for lazo, x in col.items():
        if lazo == 104:
            globo(d, x, 232, 'HS', '104', 'panel'); d.texto(x, 222.5, 'Start / S1 · I0.7', 1.5, 'TEXTO', 'centro')
            d.texto(x, 243, 'Garra / inicio', 1.8, 'TEXTO', 'centro')
            senal(d, [(x, 226), (x, 196)])
        else:
            for k, suf in ((-8, 'A'), (8, 'B')):
                globo(d, x + k, 232, 'HS', f'{lazo}{suf}', 'panel')
                senal(d, [(x + k, 226), (x + k, 214), (x, 214), (x, 196)])
            d.texto(x, 243, 'Jog ' + {101: 'base', 102: 'carro X', 103: 'carro Y'}[lazo], 1.8, 'TEXTO', 'centro')
            d.texto(x, 222.5, {101: 'S2 / S3 · I1.0 / I1.1', 102: 'S4 / S5 · I1.2 / I1.3', 103: 'S6 / S7 · I1.4 / I1.5'}[lazo], 1.5, 'TEXTO', 'centro')
        letras, nombre = tags_plc[lazo]
        globo(d, x, 190, letras, str(lazo), 'plc')
        d.texto(x, 181, nombre, 1.5, 'TEXTO', 'centro')

    # ---- base: driver y motor
    x = col[101]
    globo(d, x, 150, 'ZY', '101', 'campo'); d.texto(x - 8, 151, 'Driver 2M530', 1.7, 'TEXTO', 'der'); d.texto(x - 8, 148, 'PUL Q0.0 · DIR Q0.2', 1.5, 'TEXTO', 'der')
    senal(d, [(x, 184), (x, 156)]); senal(d, [(x, 144), (x, 100)])
    # ---- tren compartido: ZY-100 por K1 y K2
    senal(d, [(xpto, 184), (xpto, 165), (col[102] + 4, 165), (col[102] + 4, 141)])
    senal(d, [(xpto, 165), (col[103] - 4, 165), (col[103] - 4, 141)])
    d.punto(xpto, 165, 'SENAL')
    for lazo, k, q, dirq in ((102, 'K1', 'Q0.5', 'DIR Q0.3'), (103, 'K2', 'Q0.6', 'DIR Q0.4')):
        x = col[lazo]
        senal(d, [(x - 4, 184), (x - 4, 141)] if lazo == 102 else [(x + 4, 184), (x + 4, 141)])
        d.rect(x - 7, 133, x + 7, 141, 'INSTRUMENTOS'); d.texto(x, 136, k, 2.0, 'TAGS', 'centro')
        d.texto(x - 8, 138, f'{k} ({q})', 1.5, 'TEXTO', 'der'); d.texto(x - 8, 135, 'elige el eje', 1.4, 'TEXTO', 'der')
        globo(d, x, 120, 'ZY', str(lazo), 'campo')
        d.texto(x - 8, 121, 'Driver 2M542', 1.7, 'TEXTO', 'der'); d.texto(x - 8, 118, dirq, 1.5, 'TEXTO', 'der')
        senal(d, [(x, 133), (x, 126)]); senal(d, [(x, 114), (x, 100)])
    # ---- motores
    for lazo, m, desc in ((101, 'M-101', 'NEMA 17'), (102, 'M-102', 'NEMA 23'), (103, 'M-103', 'NEMA 23')):
        x = col[lazo]
        d.circulo(x, 94, 6, 'SIMBOLOS'); d.texto(x, 94, 'M', 3.0, 'TEXTO', 'centrom')
        d.texto(x - 8, 95, m, 2.0, 'TAGS', 'der'); d.texto(x - 8, 92, desc, 1.5, 'TEXTO', 'der')
        d.poli([(x, 88), (x, 50)], 'PROCESO', 1.0)
    # ---- garra
    x = col[104]
    globo(d, x, 150, 'XY', '104', 'campo'); d.texto(x - 8, 151, 'Relé K3', 1.7, 'TEXTO', 'der'); d.texto(x - 8, 148, 'Q0.7', 1.5, 'TEXTO', 'der')
    senal(d, [(x, 184), (x, 156)]); senal(d, [(x, 144), (x, 100)])
    d.rect(x - 6, 88, x + 6, 100, 'SIMBOLOS'); d.linea(x - 6, 88, x + 6, 100, 'SIMBOLOS')
    d.texto(x - 8, 95, 'XV-104', 2.0, 'TAGS', 'der'); d.texto(x - 8, 92, 'solenoide 24 V', 1.5, 'TEXTO', 'der')
    d.poli([(x, 88), (x, 50)], 'PROCESO', 1.0)

    # ---- realimentación discreta: inductivo y finales de carrera (entran al PLC por abajo)
    for lazo, tags in ((101, [('ZS', '101', 'inductivo · I0.0')]),
                       (102, [('ZSL', '102', 'atrás · I0.1'), ('ZSH', '102', 'adelante · I0.2')]),
                       (103, [('ZSL', '103', 'abajo · I0.3'), ('ZSH', '103', 'arriba · I0.4')])):
        for i, (l, n, desc) in enumerate(tags):
            gx = col[lazo] + 13 + i * 13
            globo(d, gx, 66, l, n, 'campo')
            d.texto(gx, 57.5 - 2.2 * (i % 2), desc, 1.3, 'TEXTO', 'centro')
            d.linea(gx, 50, gx, 55.5, 'PROCESO')
            senal(d, [(gx, 72), (gx, 176)])

    # ---- leyenda y notas (derecha)
    lx, ly = 248, ALTO - 22
    d.texto(lx, ly, 'LEYENDA (ISA-5.1)', 2.8, 'TEXTO')
    items = [('campo', 'Instrumento en campo'), ('panel', 'Instrumento en panel (botonera)'),
             ('plc', 'Función de PLC (lógica compartida)'), ('hmi', 'Pantalla compartida (PC / HMI)')]
    for i, (lugar, txt) in enumerate(items):
        y = ly - 12 - i * 15
        globo(d, lx + 7, y, '', '', lugar)
        d.texto(lx + 17, y - 1, txt, 2.0, 'TEXTO')
    y = ly - 12 - 4 * 15
    d.poli([(lx, y), (lx + 14, y)], 'SENAL'); d.texto(lx + 17, y - 1, 'Señal eléctrica (0,25 mm)', 2.0, 'TEXTO')
    enlace_datos(d, lx, y - 8, lx + 14, y - 8); d.texto(lx + 17, y - 9, 'Enlace de datos (software)', 2.0, 'TEXTO')
    d.poli([(lx, y - 16), (lx + 14, y - 16)], 'PROCESO', 1.0); d.texto(lx + 17, y - 17, 'Enlace mecánico / proceso (1,0 mm)', 2.0, 'TEXTO')
    d.rect(lx + 3, y - 27, lx + 11, y - 21, 'INSTRUMENTOS'); d.texto(lx + 17, y - 25, 'Relé de selección (K1, K2)', 2.0, 'TEXTO')
    letras = ['Z = posición · H = manual · X = sin clasificar', 'S = interruptor · L / H = bajo / alto',
              'I = indicación · C = control · Y = relé / conversión', 'V = válvula / actuador (solenoide)']
    for i, t in enumerate(letras):
        d.texto(lx, y - 36 - i * 4.5, t, 1.9, 'TEXTO')
    notas = ['NOTAS', '1. Posición estimada por conteo de pulsos: no hay encoders.',
             '2. Stop en paralelo con S2 (I1.0): paro en automático.',
             '3. Start en paralelo con S1 (I0.7): garra en manual, inicio en automático.',
             '4. Tags propuestos para la base de datos (tablas punto_io y variable).',
             '5. Plano eléctrico de detalle: E-B4G-01 (hojas 1 y 2).']
    for i, t in enumerate(notas):
        d.texto(lx, y - 58 - i * 4.5, t, 2.2 if i == 0 else 1.8, 'NOTAS')
    return d


# ====================================================================== símbolos IEC 60617
def contacto_na(d, x, y, capa='SIMBOLOS'):
    """Contacto normalmente abierto vertical de y (abajo) a y+10 (arriba)."""
    d.linea(x, y, x, y + 3, capa); d.linea(x, y + 7, x, y + 10, capa); d.linea(x, y + 3, x - 3, y + 7.5, capa)


def pulsador(d, x, y, nombre, desc=''):
    contacto_na(d, x, y)
    d.linea(x - 1.5, y + 5.2, x - 6, y + 5.2, 'SIMBOLOS'); d.linea(x - 6, y + 4, x - 6, y + 6.4, 'SIMBOLOS')
    d.texto(x + 1.5, y + 4.5, nombre, 2.0, 'TAGS')
    if desc:
        d.texto(x, y - 3.5, desc, 1.3, 'TEXTO', 'centro')


def final_carrera(d, x, y, nombre, desc=''):
    contacto_na(d, x, y)
    d.poli([(x - 2, y + 5.2), (x - 6, y + 7), (x - 6, y + 3.4)], 'SIMBOLOS', cerrada=True)
    d.texto(x + 1.5, y + 4.5, nombre, 2.0, 'TAGS')
    if desc:
        d.texto(x, y - 3.5, desc, 1.3, 'TEXTO', 'centro')


def bobina(d, x, y, nombre, desc=''):
    """Bobina de relé vertical: A1 abajo (y, desde la salida), A2 arriba (y+8, a 0 V)."""
    d.linea(x, y, x, y + 1.5); d.rect(x - 4, y + 1.5, x + 4, y + 6.5); d.linea(x, y + 6.5, x, y + 8)
    d.texto(x + 5, y + 3, nombre, 2.0, 'TAGS'); d.texto(x + 1, y + 7.5, 'A2', 1.2, 'BORNES'); d.texto(x + 1, y - 0.2, 'A1', 1.2, 'BORNES')
    if desc:
        d.texto(x + 5, y + 0.2, desc, 1.3, 'TEXTO')


def borne(d, x, y, t='', lado='arriba'):
    d.circulo(x, y, 0.8, 'BORNES')
    if t:
        d.texto(x, y + (1.6 if lado == 'arriba' else -3.0), t, 1.4, 'BORNES', 'centro')


def num_cable(d, x, y, t, rot=0):
    d.texto(x, y, t, 1.5, 'NUMEROS_CABLE', 'izq', rot)


def electrico():
    d = DXF()
    # ---------------------------------------------------------------- hoja 1: potencia y accionamientos
    rev1 = [
        'Drivers: X e Y 2M542 (DIP OFF OFF ON OFF ON ON ON OFF, 1000 p/vuelta); base 2M530.',
        'DIR de X e Y (Q0.3, Q0.4) conectadas a DIR+ (en el histórico no estaban).',
        'PUL+ de X e Y desde Q0.1 por los contactos de K1 y K2 (tren compartido).',
        'Motores: M1 (Y) y M2 (X) NEMA 23 2,8 A; M3 (base) NEMA 17 1,2 A.',
        'F1/F2 en las salidas de 5 V y 24 V de G1; ENA de los drivers libre (habilitado).',
    ]
    marco(d, 'ESQUEMA ELÉCTRICO · POTENCIA', 'E-B4G-01', '1 de 2', rev1, 'IEC 60617 · 60204-1')
    # alimentación
    for x, t in ((30, 'L'), (40, 'N'), (50, 'PE')):
        borne(d, x, 270, t)
    d.texto(40, 277, 'AC 220 V 50 Hz', 2.2, 'TEXTO', 'centro')
    d.linea(30, 269.2, 30, 250, 'POTENCIA'); d.linea(40, 269.2, 40, 250, 'POTENCIA')
    for x in (30, 40):                              # -Q1 disyuntor bipolar
        d.linea(x, 250, x, 247); d.linea(x, 247, x - 3, 242); d.linea(x, 240, x, 236)
        d.texto(x - 1.2, 247.5, 'x', 2.0, 'SIMBOLOS')
    d.linea(27.5, 244.5, 37.5, 244.5, 'SIMBOLOS')
    d.texto(10.5 + 2, 244, '-Q1', 2.2, 'TAGS'); d.texto(12.5, 240.5, 'DZ47LE-63', 1.4, 'TEXTO'); d.texto(12.5, 238, '16 A · 30 mA', 1.4, 'TEXTO')
    d.linea(30, 236, 30, 222, 'POTENCIA'); d.linea(40, 236, 40, 222, 'POTENCIA')
    d.linea(50, 269.2, 50, 212, 'POTENCIA')
    # -G1 fuente
    d.rect(22, 196, 62, 222)
    d.linea(22, 196, 62, 222)
    d.texto(42, 216, '-G1', 2.4, 'TAGS', 'centro'); d.texto(52, 200.5, 'AC/DC', 1.6, 'TEXTO', 'centro')
    d.texto(30, 223, 'L', 1.4, 'BORNES', 'centro'); d.texto(40, 223, 'N', 1.4, 'BORNES', 'centro'); d.texto(50, 213, 'PE', 1.4, 'BORNES', 'centro')
    for x, t in ((26, '+5V'), (34, '0V'), (48, '+24V'), (56, '0V')):
        borne(d, x, 196, '', 'abajo'); d.texto(x, 192.5, t, 1.4, 'BORNES', 'centro')
    d.texto(64, 212, 'Fuente conmutada', 1.6, 'TEXTO'); d.texto(64, 209, '220 V AC / 24 V y 5 V DC', 1.6, 'TEXTO')
    # fusibles y barras
    def fusible(x, y, n):
        d.rect(x - 1.5, y, x + 1.5, y + 7); d.linea(x, y, x, y + 7); d.texto(x + 2.5, y + 2.5, n, 1.8, 'TAGS')
    d.linea(26, 195.2, 26, 186, 'CC5'); fusible(26, 179, '-F1'); d.linea(26, 179, 26, 160, 'CC5')
    d.linea(48, 195.2, 48, 186, 'CC24'); fusible(48, 179, '-F2'); d.linea(48, 179, 48, 170, 'CC24')
    d.linea(34, 195.2, 34, 155, 'CC0V'); d.linea(56, 195.2, 56, 165, 'CC0V')
    barras = [(170, 'CC24', '+24 V  (L+)', 48), (165, 'CC0V', '0 V  (M)', 56), (160, 'CC5', '+5 V', 26), (155, 'CC0V', '0 V (5 V)', 34)]
    for y, capa, t, xi in barras:
        xf = 395 if y >= 165 else 80                  # la salida de 5 V no alimenta a los drivers
        d.linea(xi, y, xf, y, capa); d.punto(xi, y)
        d.texto(xf + 2, y - 0.8, t, 1.8, 'TEXTO')
    d.texto(70, 172, 'a hoja 2: PLC, relés, sensores (/2.1)', 1.6, 'REFERENCIAS')
    # drivers y motores
    drivers = [(120, '-A1', 'Driver eje Y', '2M542', '-M1', 'NEMA 23 · 57J1854-828 · 2,8 A', 'Q0.1 por K2 (/2.1)', 'Q0.4 (/2.3)'),
               (220, '-A2', 'Driver eje X', '2M542', '-M2', 'NEMA 23 · 57J1854-828 · 2,8 A', 'Q0.1 por K1 (/2.1)', 'Q0.3 (/2.2)'),
               (320, '-A3', 'Driver eje Z (base)', '2M530', '-M3', 'NEMA 17 · 42J1848-604 · 1,2 A', 'Q0.0 (/2.1)', 'Q0.2 (/2.2)')]
    for x, a, nombre, modelo, m, desc_m, pul, dirq in drivers:
        dy = 13                                       # los drivers suben para dejar libre el cajetín
        d.rect(x - 25, 95 + dy, x + 25, 140 + dy, 'SIMBOLOS', 0.35)
        d.texto(x, 143 + dy, f'{a}  {nombre}', 2.4, 'TAGS', 'centro'); d.texto(x, 136 + dy, modelo, 2.2, 'TEXTO', 'centro')
        izq = [('V+', 130 + dy), ('GND', 125 + dy), ('A+', 115 + dy), ('A-', 110 + dy), ('B+', 105 + dy), ('B-', 100 + dy)]
        der = [('PUL+', 130 + dy), ('PUL-', 125 + dy), ('DIR+', 119 + dy), ('DIR-', 114 + dy), ('ENA+', 106 + dy), ('ENA-', 101 + dy)]
        for t, y in izq:
            borne(d, x - 25, y); d.texto(x - 22.5, y - 0.8, t, 1.6, 'BORNES')
        for t, y in der:
            borne(d, x + 25, y); d.texto(x + 22.5, y - 0.8, t, 1.6, 'BORNES', 'der')
        # alimentación del driver
        d.linea(x - 33, 170, x - 33, 130 + dy, 'CC24'); d.punto(x - 33, 170); d.linea(x - 33, 130 + dy, x - 25.8, 130 + dy, 'CC24')
        d.linea(x - 30, 165, x - 30, 125 + dy, 'CC0V'); d.punto(x - 30, 165); d.linea(x - 30, 125 + dy, x - 25.8, 125 + dy, 'CC0V')
        num_cable(d, x - 33.5, 150 + dy / 2, '24V', 90); num_cable(d, x - 30.5, 150 + dy / 2, '0V', 90)
        # señales: PUL+ / DIR+ desde el PLC; PUL- / DIR- al común 0 V
        for y, t in ((130 + dy, pul), (119 + dy, dirq)):
            d.linea(x + 25.8, y, x + 40, y, 'MANDO'); d.linea(x + 40, y, x + 40, y + 2.5, 'MANDO')
            d.texto(x + 41, y + 0.5, t, 1.4, 'REFERENCIAS')
        for y in (125 + dy, 114 + dy):
            d.linea(x + 25.8, y, x + 31, y, 'CC0V')
        d.linea(x + 31, 114 + dy, x + 31, 165, 'CC0V'); d.punto(x + 31, 165)
        d.texto(x + 27, 104 + dy, 'libre', 1.3, 'TEXTO')
        # motor a la izquierda del driver, con sus cuatro fases
        mx, my, mr = x - 47, 120, 8
        for t, y in izq[2:]:
            borde = mx + math.sqrt(max(mr * mr - (y - my) ** 2, 0))
            d.linea(x - 25.8, y, borde, y, 'POTENCIA')
            num_cable(d, x - 35, y + 0.4, t)
        d.circulo(mx, my, mr, 'SIMBOLOS'); d.texto(mx, my + 1, 'M', 3.5, 'TEXTO', 'centrom'); d.texto(mx, my - 3.5, 'paso a paso', 1.2, 'TEXTO', 'centro')
        d.texto(mx, my - mr - 3.5, m, 2.4, 'TAGS', 'centro'); d.texto(mx, my - mr - 6.5, desc_m, 1.4, 'TEXTO', 'centro')
    d.texto(30, 86, 'Configuración DIP de -A1 y -A2 (2M542):', 2.0, 'NOTAS')
    d.texto(30, 82, 'SW1-SW3 OFF OFF ON = 2,37 A pico (1,69 A RMS)', 1.7, 'NOTAS')
    d.texto(30, 78.5, 'SW4 OFF = media corriente en reposo', 1.7, 'NOTAS')
    d.texto(30, 75, 'SW5-SW8 ON ON ON OFF = 1000 pulsos/vuelta', 1.7, 'NOTAS')
    d.texto(30, 71.5, 'VERIFICAR: tabla de corriente del 2M530 (motor de 1,2 A)', 1.7, 'NOTAS')
    d.texto(30, 68, 'VERIFICAR: PUL/DIR son optoacopladas de 5 V; con 24 V del PLC', 1.7, 'NOTAS')
    d.texto(30, 64.5, 'van con resistencia en serie o desde el riel de 5 V (SUPUESTO).', 1.7, 'NOTAS')

    # ---------------------------------------------------------------- hoja 2: mando (PLC)
    d.dx = ANCHO + 30
    rev2 = [
        'Entradas: B1 inductivo I0.0; S11-S14 finales I0.1-I0.4 (X atrás/adelante, Y abajo/arriba).',
        'Start en paralelo con S1 (I0.7); Stop en paralelo con S2 (I1.0).',
        '-K3 dibujado de nuevo: bobina por Q0.7, contacto 9-5 al solenoide -Y1.',
        'Salidas Q0.3 y Q0.4 conectadas (en el histórico figuraban sin conexión).',
        'Referencias cruzadas de K1, K2 y K3 y tabla de E/S con tags ISA-5.1.',
    ]
    marco(d, 'ESQUEMA ELÉCTRICO · MANDO (PLC)', 'E-B4G-01', '2 de 2', rev2, 'IEC 60617 · 60204-1')
    # barras
    for y, capa, t in ((262, 'CC24', '+24 V (L+)  de /1.2'), (256, 'CC0V', '0 V (M)  de /1.2')):
        d.linea(20, y, 240, y, capa); d.texto(20, y + 1.2, t, 1.7, 'TEXTO')
    # PLC
    px0, px1, py0, py1 = 30, 230, 150, 200
    d.rect(px0, py0, px1, py1, 'SIMBOLOS', 0.35)
    d.texto(px0 + 4, 186, '-A4  PLC Siemens S7-200 CPU 224 CN DC/DC/DC', 2.6, 'TAGS')
    d.texto(px0 + 4, 181.5, '6ES7 214-1AD23-0XB8 · 14 DI / 10 DO 24 V DC · puerto 0 RS-485 (PPI)', 1.8, 'TEXTO')
    d.texto(px0 + 4, 158, 'Entradas DC 24 V (grupo 1: I0.0-I0.7 · grupo 2: I1.0-I1.5)', 1.7, 'TEXTO')
    salidas = ['1M', '1L+', 'Q0.0', 'Q0.1', 'Q0.2', 'Q0.3', 'Q0.4', '2M', '2L+', 'Q0.5', 'Q0.6', 'Q0.7', 'Q1.0', 'Q1.1']
    xs = {t: px0 + 8 + i * 14.3 for i, t in enumerate(salidas)}
    for t, x in xs.items():
        borne(d, x, py1); d.texto(x, py1 - 4, t, 1.5, 'BORNES', 'centro')
    # alimentación de las salidas
    for t, y, capa in (('1L+', 262, 'CC24'), ('2L+', 262, 'CC24'), ('1M', 256, 'CC0V'), ('2M', 256, 'CC0V')):
        d.linea(xs[t], py1 + 0.8, xs[t], y, capa); d.punto(xs[t], y)
    # salidas de pulsos y dirección hacia la hoja 1
    dest = {'Q0.0': 'PUL+ -A3 (/1.7)', 'Q0.2': 'DIR+ -A3 (/1.7)', 'Q0.3': 'DIR+ -A2 (/1.5)', 'Q0.4': 'DIR+ -A1 (/1.3)'}
    for t, txt in dest.items():
        d.linea(xs[t], py1 + 0.8, xs[t], 240, 'MANDO')
        d.texto(xs[t] + 0.8, 241, txt, 1.4, 'REFERENCIAS', 'izq', 90)
        num_cable(d, xs[t] + 0.8, 212, t.replace('Q', 'W'), 90)
    # Q0.1 por K1 y K2
    x1 = xs['Q0.1']
    d.linea(x1, py1 + 0.8, x1, 222, 'MANDO'); d.punto(x1, 222); d.linea(x1 - 6, 222, x1 + 6, 222, 'MANDO')
    for xk, k, dst in ((x1 - 6, '-K1', 'PUL+ -A2 (/1.5)'), (x1 + 6, '-K2', 'PUL+ -A1 (/1.3)')):
        d.linea(xk, 222, xk, 225, 'MANDO'); contacto_na(d, xk, 225, 'MANDO'); d.linea(xk, 235, xk, 240, 'MANDO')
        d.texto(xk + 1.3, 229, k, 1.6, 'TAGS'); d.texto(xk + 1.3, 226, '9-5', 1.1, 'BORNES')
        d.texto(xk + 0.8, 241, dst, 1.4, 'REFERENCIAS', 'izq', 90)
    num_cable(d, x1 + 0.8, 210, 'W0.1', 90)
    # bobinas K1, K2, K3
    for t, k, desc, ref in (('Q0.5', '-K1', 'driver X', '9-5 /2.1'),
                            ('Q0.6', '-K2', 'driver Y', '9-5 /2.1'),
                            ('Q0.7', '-K3', 'garra', '9-5 /2.5')):
        x = xs[t]
        d.linea(x, py1 + 0.8, x, 228, 'MANDO')
        bobina(d, x, 228, k, '')
        d.linea(x, 236, x, 256, 'CC0V'); d.punto(x, 256)
        d.texto(x, 224.5, desc, 1.3, 'TEXTO', 'centro'); d.texto(x, 222, ref, 1.3, 'REFERENCIAS', 'centro')
    d.texto(xs['Q0.6'], 216.5, 'Relés Omron MY2N-J 24 V DC', 1.5, 'TEXTO', 'centro')
    d.texto(xs['Q0.6'], 213.5, 'bobina 13-14 · contacto COM 9 / NA 5', 1.3, 'TEXTO', 'centro')
    # garra: contacto de K3 y solenoide (circuito aparte, a la derecha)
    gx = 250
    d.texto(gx, 181, '+24 V (L+) /2.1', 1.5, 'REFERENCIAS', 'centro')
    borne(d, gx, 178); d.linea(gx, 177.2, gx, 170, 'CC24')
    contacto_na(d, gx, 160); d.texto(gx + 1.5, 164, '-K3', 1.8, 'TAGS'); d.texto(gx + 1.5, 161, '9-5', 1.1, 'BORNES')
    d.texto(gx + 8, 164, 'contacto de K3 (bobina /2.4)', 1.3, 'REFERENCIAS')
    d.linea(gx, 160, gx, 150, 'MANDO')
    d.rect(gx - 4, 142, gx + 4, 150); d.linea(gx - 4, 142, gx + 4, 150)
    d.texto(gx + 6, 146.5, '-Y1  solenoide de la garra 24 V', 1.6, 'TAGS'); d.texto(gx + 6, 143.5, 'Q0.7 = 1: garra cerrada', 1.3, 'TEXTO')
    d.linea(gx, 142, gx, 131.2, 'CC0V'); borne(d, gx, 130); d.texto(gx, 126, '0 V (M) /2.1', 1.5, 'REFERENCIAS', 'centro')
    # entradas
    entradas = ['1M', 'I0.0', 'I0.1', 'I0.2', 'I0.3', 'I0.4', 'I0.5', 'I0.6', 'I0.7', '2M', 'I1.0', 'I1.1', 'I1.2', 'I1.3', 'I1.4', 'I1.5']
    xe = {t: px0 + 8 + i * 12.5 for i, t in enumerate(entradas)}
    for t, x in xe.items():
        borne(d, x, py0, '', 'abajo'); d.texto(x, py0 + 2, t, 1.5, 'BORNES', 'centro')
    # comunes de entradas a 0 V (entrada tipo sumidero, esquema típico)
    d.linea(20, 140, 236, 140, 'CC24'); d.texto(20, 141, '+24 V (L+)', 1.6, 'TEXTO')
    d.linea(20, 74, 236, 74, 'CC0V'); d.texto(20, 75, '0 V (M)', 1.6, 'TEXTO')
    for t in ('1M', '2M'):
        d.linea(xe[t], py0 - 0.8, xe[t], 140, 'CC24'); d.punto(xe[t], 140)
    dispositivos = {
        'I0.0': ('sensor', '-B1', 'inductivo base = 0'), 'I0.1': ('final', '-S11', 'X atrás'), 'I0.2': ('final', '-S12', 'X adelante'),
        'I0.3': ('final', '-S13', 'Y abajo'), 'I0.4': ('final', '-S14', 'Y arriba'), 'I0.5': ('selector', '-QA', 'man/auto'),
        'I0.6': ('pulsador', 'Reset', 'paro'), 'I0.7': ('doble', 'Start', 'S1'), 'I1.0': ('doble', 'Stop', 'S2'),
        'I1.1': ('pulsador', 'S3', 'base -'), 'I1.2': ('pulsador', 'S4', 'X +'), 'I1.3': ('pulsador', 'S5', 'X -'),
        'I1.4': ('pulsador', 'S6', 'Y +'), 'I1.5': ('pulsador', 'S7', 'Y -'),
    }
    for t, (tipo, nombre, desc) in dispositivos.items():
        x = xe[t]
        d.linea(x, py0 - 0.8, x, 112, 'MANDO')
        num_cable(d, x + 0.8, 120, t.replace('I', 'E'), 90)
        if tipo == 'sensor':
            d.rect(x - 5, 96, x + 5, 108); d.poli([(x - 3, 102), (x, 105), (x + 3, 102), (x, 99)], 'SIMBOLOS', cerrada=True)
            d.linea(x, 108, x, 112, 'MANDO')
            d.texto(x, 92, nombre, 1.8, 'TAGS', 'centro'); d.texto(x, 89.5, 'LJ12A3-4-Z/BX NPN', 1.2, 'TEXTO', 'centro')
            d.texto(x + 1, 110, 'BK', 1.2, 'BORNES'); d.texto(x - 3, 93.5, 'BN', 1.2, 'BORNES', 'der'); d.texto(x + 3, 93.5, 'BU', 1.2, 'BORNES')
            d.linea(x + 2, 96, x + 2, 74, 'CC0V'); d.punto(x + 2, 74); d.poli([(x - 2, 96), (x - 2, 94), (x - 9, 94), (x - 9, 140)], 'CC24'); d.punto(x - 9, 140)
            d.texto(x, 86.5, desc, 1.2, 'TEXTO', 'centro')
            continue
        if tipo == 'doble':
            d.linea(x, 112, x, 106, 'MANDO'); d.linea(x - 4, 106, x + 4, 106, 'MANDO'); d.punto(x, 106)
            for k, n in ((-4, nombre), (4, desc)):
                d.linea(x + k, 106, x + k, 100, 'MANDO'); pulsador(d, x + k, 90, '', '')
                d.texto(x + k, 86.5, n, 1.4, 'TAGS', 'centro')
                d.linea(x + k, 90, x + k, 74, 'CC0V'); d.punto(x + k, 74)
            continue
        d.linea(x, 112, x, 100, 'MANDO')
        (final_carrera if tipo == 'final' else pulsador)(d, x, 90, '', '')
        d.texto(x, 86.5, nombre, 1.6, 'TAGS', 'centro'); d.texto(x, 84, desc, 1.2, 'TEXTO', 'centro')
        d.linea(x, 90, x, 74, 'CC0V'); d.punto(x, 74)
    d.texto(30, 66, 'Comunes 1M y 2M a +24 V: el sensor NPN de I0.0 cierra a 0 V, igual que los contactos (SUPUESTO).', 1.6, 'NOTAS')
    d.texto(30, 62.5, 'VERIFICAR en el tablero: comunes 1M/2M, cableado de -B1 y numeración del zócalo de K1-K3.', 1.6, 'NOTAS')
    d.texto(30, 59, 'Correspondencia LS1-LS4 del plano histórico con S11-S14: SUPUESTO por orden.', 1.6, 'NOTAS')
    # tabla de E/S con tags
    tx, ty = 262, ALTO - 18
    d.texto(tx, ty, 'TABLA DE E/S (tags ISA-5.1)', 2.6, 'TEXTO')
    filas = [('I0.0', 'ZS-101', 'Inductivo base = 0'), ('I0.1', 'ZSL-102', 'Final X atrás (origen)'), ('I0.2', 'ZSH-102', 'Final X adelante'),
             ('I0.3', 'ZSL-103', 'Final Y abajo (origen)'), ('I0.4', 'ZSH-103', 'Final Y arriba'), ('I0.5', 'HS-100', 'Selector man / auto'),
             ('I0.6', 'HS-100P', 'Reset: paro'), ('I0.7', 'HS-104', 'Start / S1: garra o inicio'), ('I1.0', 'HS-101A', 'S2 jog base + · Stop'),
             ('I1.1', 'HS-101B', 'S3 jog base -'), ('I1.2', 'HS-102A', 'S4 jog X adelante'), ('I1.3', 'HS-102B', 'S5 jog X atrás'),
             ('I1.4', 'HS-103A', 'S6 jog Y arriba'), ('I1.5', 'HS-103B', 'S7 jog Y abajo'),
             ('Q0.0', 'ZY-101', 'PUL base (PTO0)'), ('Q0.1', 'ZY-100', 'PUL X/Y compartido (PTO1)'), ('Q0.2', 'ZY-101D', 'DIR base'),
             ('Q0.3', 'ZY-102D', 'DIR X (0 = adelante)'), ('Q0.4', 'ZY-103D', 'DIR Y (0 = arriba)'), ('Q0.5', 'ZY-102K', 'K1: tren al driver X'),
             ('Q0.6', 'ZY-103K', 'K2: tren al driver Y'), ('Q0.7', 'XY-104', 'K3: solenoide de la garra')]
    d.rect(tx, ty - 6 - 4 * len(filas), ANCHO - 12, ty - 3, 'TEXTO')
    d.texto(tx + 1.5, ty - 5.2, 'Dir.', 1.7, 'TEXTO'); d.texto(tx + 13, ty - 5.2, 'Tag', 1.7, 'TEXTO'); d.texto(tx + 33, ty - 5.2, 'Función', 1.7, 'TEXTO')
    for i, (a, tg, f) in enumerate(filas):
        y = ty - 9.6 - i * 4
        d.linea(tx, y + 3.2, ANCHO - 12, y + 3.2, 'TEXTO')
        d.texto(tx + 1.5, y, a, 1.6, 'TEXTO'); d.texto(tx + 13, y, tg, 1.6, 'TAGS'); d.texto(tx + 33, y, f, 1.6, 'TEXTO')
    return d


# ====================================================================== PDF (opcional, con matplotlib)
COLOR_ACI = {1: '#d00000', 2: '#a07800', 3: '#008000', 4: '#008b8b', 5: '#0030c0', 6: '#b000b0', 7: '#000000', 8: '#707070'}


def leer_dxf(ruta):
    """Lee las entidades que escribe la clase DXF (para dibujarlas en PDF)."""
    with open(ruta, encoding='cp1252') as f:
        filas = f.read().split('\n')
    pares = [(filas[i].strip(), filas[i + 1].rstrip('\r')) for i in range(0, len(filas) - 1, 2)]
    i = next(k for k, (c, v) in enumerate(pares) if c == '2' and v == 'ENTITIES') + 1
    ents, actual = [], None
    for c, v in pares[i:]:
        if c == '0':
            actual = {'tipo': v, 'pts': []}
            ents.append(actual)
            continue
        if c in ('10', '11', '12', '13'):
            actual.setdefault('x' + c, float(v))
        elif c in ('20', '21', '22', '23'):
            actual.setdefault('y' + c, float(v))
        else:
            actual.setdefault(c, v)
    salida, poli = [], None
    for e in ents:
        if e['tipo'] == 'POLYLINE':
            poli = e
        elif e['tipo'] == 'VERTEX' and poli is not None:
            poli['pts'].append((e['x10'], e['y20']))
        elif e['tipo'] == 'SEQEND':
            salida.append(poli); poli = None
        elif e['tipo'] in ('LINE', 'CIRCLE', 'ARC', 'TEXT', 'SOLID'):
            salida.append(e)
    return salida


def a_pdf(ruta_dxf, ruta_pdf, hojas):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Circle, Arc, Polygon
    ents = leer_dxf(ruta_dxf)
    mm = 1 / 25.4
    with PdfPages(ruta_pdf) as pdf:
        for x0 in hojas:
            fig = plt.figure(figsize=(ANCHO * mm, ALTO * mm))
            ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(x0, x0 + ANCHO); ax.set_ylim(0, ALTO); ax.axis('off')
            for e in ents:
                capa = e.get('8', '0')
                col = COLOR_ACI.get(CAPAS.get(capa, (7,))[0], '#000')
                estilo = '--' if CAPAS.get(capa, (7, ''))[1] == 'DASHED' else '-'
                if e['tipo'] == 'LINE':
                    xs = (e['x10'], e['x11'])
                    if max(xs) < x0 or min(xs) > x0 + ANCHO:
                        continue
                    ax.plot(xs, (e['y20'], e['y21']), estilo, color=col, lw=0.35, dashes=(6, 3) if estilo == '--' else (None, None))
                elif e['tipo'] == 'POLYLINE':
                    pts = e['pts'] + ([e['pts'][0]] if e.get('70') == '1' else [])
                    if not pts or pts[0][0] < x0 - 1 or pts[0][0] > x0 + ANCHO + 1:
                        continue
                    w = float(e.get('40', 0) or 0)
                    ax.plot([p[0] for p in pts], [p[1] for p in pts], estilo, color=col,
                            lw=max(0.35, w / 0.3528), dashes=(6, 3) if estilo == '--' else (None, None))
                elif e['tipo'] in ('CIRCLE', 'ARC'):
                    if not x0 <= e['x10'] <= x0 + ANCHO:
                        continue
                    r = float(e['40'])
                    if e['tipo'] == 'CIRCLE':
                        ax.add_patch(Circle((e['x10'], e['y20']), r, fill=False, color=col, lw=0.35))
                    else:
                        ax.add_patch(Arc((e['x10'], e['y20']), 2 * r, 2 * r, theta1=float(e['50']), theta2=float(e['51']), color=col, lw=0.35))
                elif e['tipo'] == 'SOLID':
                    if not x0 <= e['x10'] <= x0 + ANCHO:
                        continue
                    ax.add_patch(Polygon([(e['x10'], e['y20']), (e['x11'], e['y21']), (e['x13'], e['y23']), (e['x12'], e['y22'])], color=col))
                elif e['tipo'] == 'TEXT':
                    x, y = (e['x11'], e['y21']) if '72' in e or '73' in e else (e['x10'], e['y20'])
                    if not x0 - 5 <= x <= x0 + ANCHO:
                        continue
                    ha = {'0': 'left', '1': 'center', '2': 'right'}[e.get('72', '0')]
                    va = 'center' if e.get('73') == '2' else 'baseline'
                    ax.text(x, y, e['1'], fontsize=float(e['40']) * 72 / 25.4 * 1.32, ha=ha, va=va, color=col,
                            rotation=float(e.get('50', 0)), rotation_mode='anchor', family='DejaVu Sans Condensed' if False else 'DejaVu Sans')
            pdf.savefig(fig); plt.close(fig)


if __name__ == '__main__':
    os.makedirs(os.path.join(AQUI, 'pid'), exist_ok=True)
    os.makedirs(os.path.join(AQUI, 'electrico'), exist_ok=True)
    pid().guardar(os.path.join(AQUI, 'pid', 'brazo_pid_v2.dxf'))
    electrico().guardar(os.path.join(AQUI, 'electrico', 'brazo_electrico_v2.dxf'))
    print('generados: pid/brazo_pid_v2.dxf y electrico/brazo_electrico_v2.dxf')
    try:
        a_pdf(os.path.join(AQUI, 'pid', 'brazo_pid_v2.dxf'), os.path.join(AQUI, 'pid', 'brazo_pid_v2.pdf'), [0])
        a_pdf(os.path.join(AQUI, 'electrico', 'brazo_electrico_v2.dxf'), os.path.join(AQUI, 'electrico', 'brazo_electrico_v2.pdf'), [0, ANCHO + 30])
        print('y sus PDF (A3)')
    except ImportError:
        print('sin matplotlib: PDF no generado')
