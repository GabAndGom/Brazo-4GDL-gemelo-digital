"""Código QR sin dependencias: modo byte, corrección de errores M, versiones 1 a 10.

    matriz('https://192.168.1.37:8443/')   -> lista de filas de 0/1
    svg('https://192.168.1.37:8443/')      -> texto SVG listo para una página

Alcanza para direcciones de hasta 213 bytes (versión 10). Sigue la norma ISO/IEC 18004.
"""

# (codewords totales, codewords de corrección por bloque, [(bloques, datos por bloque), ...]) nivel M
_TABLA_M = {
    1: (26, 10, [(1, 16)]), 2: (44, 16, [(1, 28)]), 3: (70, 26, [(1, 44)]), 4: (100, 18, [(2, 32)]),
    5: (134, 24, [(2, 43)]), 6: (172, 16, [(4, 27)]), 7: (196, 18, [(4, 31)]),
    8: (242, 22, [(2, 38), (2, 39)]), 9: (292, 22, [(3, 36), (2, 37)]), 10: (346, 26, [(4, 43), (1, 44)]),
}
_ALINEACION = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
               7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}
_RESTO = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7, 7: 0, 8: 0, 9: 0, 10: 0}

# ---------------------------------------------------------------- Reed-Solomon en GF(256)
_EXP, _LOG = [0] * 512, [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i], _LOG[_x] = _x, _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _generador(n):
    g = [1]
    for i in range(n):
        g = [(g[j] if j < len(g) else 0) ^ (_mul(g[j - 1], _EXP[i]) if j > 0 else 0) for j in range(len(g) + 1)]
    return g


def _correccion(datos, n):
    g = _generador(n)
    resto = list(datos) + [0] * n
    for i in range(len(datos)):
        c = resto[i]
        if c:
            for j in range(1, len(g)):
                resto[i + j] ^= _mul(g[j], c)
    return resto[len(datos):]


# ---------------------------------------------------------------- datos
def _version(n_bytes):
    for v, (total, ec, grupos) in _TABLA_M.items():
        capacidad = sum(b * d for b, d in grupos)
        bits = 4 + (8 if v < 10 else 16) + 8 * n_bytes
        if bits <= capacidad * 8:
            return v
    raise ValueError('texto demasiado largo para el código QR (máximo 213 bytes)')


def _codewords(texto, v):
    datos = texto.encode('utf-8')
    total, ec, grupos = _TABLA_M[v]
    capacidad = sum(b * d for b, d in grupos)
    bits = '0100' + format(len(datos), '08b' if v < 10 else '016b') + ''.join(format(b, '08b') for b in datos)
    bits += '0' * min(4, capacidad * 8 - len(bits))
    bits += '0' * (-len(bits) % 8)
    cw = [int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)]
    relleno = [0xEC, 0x11]
    while len(cw) < capacidad:
        cw.append(relleno[(len(cw) - len(bits) // 8) % 2])
    bloques, i = [], 0
    for n, d in grupos:
        for _ in range(n):
            bloques.append(cw[i:i + d])
            i += d
    correcciones = [_correccion(b, ec) for b in bloques]
    salida = []
    for k in range(max(len(b) for b in bloques)):
        salida += [b[k] for b in bloques if k < len(b)]
    for k in range(ec):
        salida += [c[k] for c in correcciones]
    return salida


# ---------------------------------------------------------------- matriz
_MASCARAS = [
    lambda f, c: (f + c) % 2 == 0, lambda f, c: f % 2 == 0, lambda f, c: c % 3 == 0,
    lambda f, c: (f + c) % 3 == 0, lambda f, c: (f // 2 + c // 3) % 2 == 0,
    lambda f, c: (f * c) % 2 + (f * c) % 3 == 0, lambda f, c: ((f * c) % 2 + (f * c) % 3) % 2 == 0,
    lambda f, c: ((f + c) % 2 + (f * c) % 3) % 2 == 0,
]


def _bch(valor, generador, bits_gen):
    v = valor << (bits_gen - 1)
    while v.bit_length() >= bits_gen:
        v ^= generador << (v.bit_length() - bits_gen)
    return v


def _base(v):
    n = 17 + 4 * v
    m = [[None] * n for _ in range(n)]

    def poner(f, c, b):
        if 0 <= f < n and 0 <= c < n:
            m[f][c] = b

    for (f0, c0) in ((0, 0), (0, n - 7), (n - 7, 0)):          # buscadores con separador
        for df in range(-1, 8):
            for dc in range(-1, 8):
                dentro = 0 <= df <= 6 and 0 <= dc <= 6
                borde = df in (0, 6) or dc in (0, 6)
                centro = 2 <= df <= 4 and 2 <= dc <= 4
                poner(f0 + df, c0 + dc, 1 if dentro and (borde or centro) else 0)
    for i in range(8, n - 8):                                   # patrones de sincronismo
        m[6][i] = m[i][6] = 1 if i % 2 == 0 else 0
    pos = _ALINEACION[v]
    for f in pos:
        for c in pos:
            if (f < 9 and c < 9) or (f < 9 and c > n - 10) or (f > n - 10 and c < 9):
                continue                                        # se superpone con un buscador
            for df in range(-2, 3):
                for dc in range(-2, 3):
                    m[f + df][c + dc] = 1 if max(abs(df), abs(dc)) != 1 else 0
    m[n - 8][8] = 1                                             # módulo oscuro
    for i in range(9):                                          # zonas de formato reservadas
        if m[8][i] is None:
            m[8][i] = 0
        if m[i][8] is None:
            m[i][8] = 0
    for i in range(8):
        if m[8][n - 1 - i] is None:
            m[8][n - 1 - i] = 0
        if m[n - 1 - i][8] is None:
            m[n - 1 - i][8] = 0
    if v >= 7:                                                  # información de versión
        info = (v << 12) | _bch(v, 0x1F25, 13)
        for i in range(18):
            b = (info >> i) & 1
            m[i // 3][n - 11 + i % 3] = b
            m[n - 11 + i % 3][i // 3] = b
    return m


def _colocar(m, cw, v):
    n = len(m)
    bits = ''.join(format(c, '08b') for c in cw) + '0' * _RESTO[v]
    libre = [[m[f][c] is None for c in range(n)] for f in range(n)]
    i, c, arriba = 0, n - 1, True
    while c > 0:
        if c == 6:
            c -= 1
        for k in range(n):
            f = n - 1 - k if arriba else k
            for cc in (c, c - 1):
                if libre[f][cc]:
                    m[f][cc] = int(bits[i]) if i < len(bits) else 0
                    i += 1
        arriba = not arriba
        c -= 2
    return libre


def _formato(m, mascara):
    n = len(m)
    datos = (0b00 << 3) | mascara                                 # nivel M = 00
    fmt = ((datos << 10) | _bch(datos, 0x537, 11)) ^ 0x5412
    bits = [(fmt >> i) & 1 for i in range(15)]
    for i in range(6):
        m[i][8] = bits[i]
    m[7][8], m[8][8], m[8][7] = bits[6], bits[7], bits[8]
    for i in range(9, 15):
        m[8][14 - i] = bits[i]
    for i in range(8):
        m[8][n - 1 - i] = bits[i]
    for i in range(8, 15):
        m[n - 15 + i][8] = bits[i]
    m[n - 8][8] = 1


def _penalizacion(m):
    n, p = len(m), 0
    for filas in (m, [list(col) for col in zip(*m)]):
        for fila in filas:
            racha, prev = 0, None
            for b in fila:
                if b == prev:
                    racha += 1
                else:
                    if racha >= 5:
                        p += racha - 2
                    racha, prev = 1, b
            if racha >= 5:
                p += racha - 2
            s = ''.join(map(str, fila))
            p += 40 * sum(s.count(pat) for pat in ('10111010000', '00001011101'))
    for f in range(n - 1):
        for c in range(n - 1):
            if m[f][c] == m[f + 1][c] == m[f][c + 1] == m[f + 1][c + 1]:
                p += 3
    oscuros = sum(map(sum, m))
    p += 10 * (abs(oscuros * 20 - n * n * 10) // (n * n))
    return p


def matriz(texto, mascara=None):
    v = _version(len(texto.encode('utf-8')))
    cw = _codewords(texto, v)
    mejor = None
    for k in ([mascara] if mascara is not None else range(8)):
        m = _base(v)
        libre = _colocar(m, cw, v)
        for f in range(len(m)):
            for c in range(len(m)):
                if libre[f][c] and _MASCARAS[k](f, c):
                    m[f][c] ^= 1
        _formato(m, k)
        p = _penalizacion(m)
        if mejor is None or p < mejor[0]:
            mejor = (p, m)
    return mejor[1]


def svg(texto, modulo=8, margen=4, color='#111', fondo='#fff'):
    m = matriz(texto)
    n = len(m) + 2 * margen
    trazos = ''.join(f'M{c + margen},{f + margen}h1v1h-1z' for f, fila in enumerate(m) for c, b in enumerate(fila) if b)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="{n * modulo}" height="{n * modulo}" '
            f'shape-rendering="crispEdges" role="img" aria-label="Código QR: {texto}">'
            f'<rect width="{n}" height="{n}" fill="{fondo}"/><path d="{trazos}" fill="{color}"/></svg>')
