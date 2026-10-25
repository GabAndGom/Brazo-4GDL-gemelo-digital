"""
Genera los esquemas acotados de la planilla de mediciones (vista lateral y superior).

    python3 semestres/2026_II/modelo-3d/levantamiento/generar_esquema_medidas.py

Toma las cotas y la pose de web/js/cinematica.js (con Node), así que las proporciones
son las del modelo. Cada cota lleva el código de su fila en la planilla (ej. 5.9 = L9).
Escribe esquema_medidas_lateral.svg y esquema_medidas_superior.svg en esta carpeta.
"""
import json
import os
import subprocess

DIR = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(DIR, "..", "..", "..", ".."))
POSE = {"theta": 0, "sX": 60, "sY": 70}

datos = json.loads(subprocess.check_output([
    "node", "-e",
    "const K=require('./web/js/cinematica.js');const f=K.directa(%s);"
    "console.log(JSON.stringify({p:K.parametros,d:K.derivados,f}))" % json.dumps(POSE)], cwd=RAIZ))
P, D, F = datos["p"], datos["d"], datos["f"]
PT = F["puntos"]

NARANJA, AZUL, VERDE, MORADO, GRIS = "#c2620c", "#2f7fc1", "#229954", "#7d3c98", "#5b6472"
ESTILO = """<style>
  text { font-family: 'IBM Plex Sans', Arial, sans-serif; }
  .pieza { stroke: #2b313b; stroke-width: 1.2; }
  .acero { stroke: #5b6472; stroke-width: 3; }
  .cota { stroke: %s; stroke-width: 1.1; fill: none; }
  .ext { stroke: %s; stroke-width: 0.7; stroke-dasharray: 3 3; }
  .cod { fill: #fff; stroke: %s; stroke-width: 1.2; }
  .codt { fill: %s; font-size: 12px; font-weight: 700; }
  .num { fill: #2b313b; font-size: 11px; }
  .tit { fill: #171b22; font-size: 16px; font-weight: 700; }
  .sub { fill: #5b6472; font-size: 11.5px; }
</style>""" % (NARANJA, NARANJA, NARANJA, NARANJA)
FLECHA = """<defs><marker id="f" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6"
  orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="%s"/></marker></defs>""" % NARANJA


class Lienzo:
    def __init__(self, ancho, alto, esc, x0, y0):
        self.w, self.h, self.s, self.x0, self.y0 = ancho, alto, esc, x0, y0
        self.el = []

    def X(self, u): return self.x0 + u * self.s
    def Y(self, h): return self.y0 - h * self.s

    def add(self, s): self.el.append(s)

    def rect(self, u0, h0, u1, h1, cls="pieza", extra=""):
        x0, x1 = sorted([self.X(u0), self.X(u1)]); y0, y1 = sorted([self.Y(h0), self.Y(h1)])
        if "fill=" not in extra:
            extra += ' fill="#eef0f3"'
        self.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1-x0:.1f}" height="{y1-y0:.1f}" class="{cls}" {extra}/>')

    def linea(self, p, q, color="#2b313b", ancho=1.2, extra=""):
        self.add(f'<line x1="{self.X(p[0]):.1f}" y1="{self.Y(p[1]):.1f}" x2="{self.X(q[0]):.1f}" y2="{self.Y(q[1]):.1f}" '
                 f'stroke="{color}" stroke-width="{ancho}" {extra}/>')

    def poli(self, pts, fill, stroke="#2b313b"):
        s = " ".join(f"{self.X(u):.1f},{self.Y(h):.1f}" for u, h in pts)
        self.add(f'<polygon points="{s}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')

    def piv(self, p, letra=None, dx=8, dy=-8):
        self.add(f'<circle cx="{self.X(p[0]):.1f}" cy="{self.Y(p[1]):.1f}" r="5" fill="#fff" stroke="#111" stroke-width="2"/>')
        if letra:
            self.add(f'<text x="{self.X(p[0])+dx:.1f}" y="{self.Y(p[1])+dy:.1f}" font-size="14" font-weight="700">{letra}</text>')

    def texto(self, p, t, cls="num", anchor="start", dx=0, dy=0):
        self.add(f'<text x="{self.X(p[0])+dx:.1f}" y="{self.Y(p[1])+dy:.1f}" class="{cls}" text-anchor="{anchor}">{t}</text>')

    def codigo(self, x, y, t):
        w = 7.4 * len(t) + 10
        self.add(f'<rect x="{x-w/2:.1f}" y="{y-10:.1f}" width="{w:.1f}" height="19" rx="9" class="cod"/>'
                 f'<text x="{x:.1f}" y="{y+4:.1f}" class="codt" text-anchor="middle">{t}</text>')

    def cota(self, p, q, off, t, pos=0.5, lab=(0, 0)):
        """Cota alineada entre p y q, desplazada 'off' mm a la izquierda del sentido p->q.
        lab = desplazamiento de la etiqueta (mm); si no es cero, se dibuja una línea guía."""
        du, dh = q[0] - p[0], q[1] - p[1]
        L = (du * du + dh * dh) ** 0.5
        nu, nh = -dh / L, du / L
        a = (p[0] + nu * off, p[1] + nh * off); b = (q[0] + nu * off, q[1] + nh * off)
        for e, f in ((p, a), (q, b)):
            self.add(f'<line x1="{self.X(e[0]):.1f}" y1="{self.Y(e[1]):.1f}" x2="{self.X(f[0]):.1f}" y2="{self.Y(f[1]):.1f}" class="ext"/>')
        self.add(f'<line x1="{self.X(a[0]):.1f}" y1="{self.Y(a[1]):.1f}" x2="{self.X(b[0]):.1f}" y2="{self.Y(b[1]):.1f}" '
                 f'class="cota" marker-start="url(#f)" marker-end="url(#f)"/>')
        m = (a[0] + (b[0] - a[0]) * pos, a[1] + (b[1] - a[1]) * pos)
        k = (m[0] + lab[0], m[1] + lab[1])
        if lab != (0, 0):
            self.add(f'<line x1="{self.X(m[0]):.1f}" y1="{self.Y(m[1]):.1f}" x2="{self.X(k[0]):.1f}" y2="{self.Y(k[1]):.1f}" '
                     f'stroke="{NARANJA}" stroke-width="0.8"/>')
        self.codigo(self.X(k[0]), self.Y(k[1]), t)

    def svg(self, titulo, sub):
        cab = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}">'
               f'<title>{titulo}</title>{ESTILO}{FLECHA}<rect width="{self.w}" height="{self.h}" fill="#fff"/>'
               f'<text x="20" y="28" class="tit">{titulo}</text><text x="20" y="47" class="sub">{sub}</text>')
        return cab + "\n".join(self.el) + "</svg>"


# ======================================================================= vista lateral
L = Lienzo(1280, 760, 1.25, 430, 690)
u5 = D["u5_0"] + POSE["sX"]                       # cara interior de la placa 5
e = P["espesorPlaca"]; libre = P["largoGuias"] - 2 * e
u10 = u5 - libre                                  # cara interior de la placa 10
hx, hy = D["hEjeX"], D["hEjeY"]
hplaca = (hx + hy) / 2
# mesa
L.add(f'<line x1="20" y1="{L.Y(0)}" x2="1260" y2="{L.Y(0)}" stroke="#2b313b" stroke-width="2"/>')
L.texto((-330, 0), "mesa", "sub", dy=16)
# base
r = P["rDisco"]
L.rect(-r, 0, r, P["hDiscoInf"]); h1 = P["hDiscoInf"] + P["hEntreDiscos"]
L.rect(-25, P["hDiscoInf"], 25, h1, "pieza", 'fill="#d5d8dc"')
L.rect(-r, h1, r, h1 + P["hDiscoSup"])
hc = h1 + P["hDiscoSup"]
L.rect(-35.5, hc, 35.5, hc + P["hColumna"])
L.add(f'<line x1="{L.X(0)}" y1="{L.Y(-5)}" x2="{L.X(0)}" y2="{L.Y(430)}" stroke="#c0392b" stroke-width="1" stroke-dasharray="10 4 2 4"/>')
L.texto((0, 430), "eje θ", "sub", "middle", dy=-6)
L.rect(40, hc, 82, hc + 48, "pieza", 'fill="#2b313b"')
# bloque 2 y bloque 1
L.rect(-P["largoBloque"] / 2, hx - P["hBloque2"] / 2, P["largoBloque"] / 2, hx + P["hBloque2"] / 2, "pieza", 'fill="#cfd8dc"')
b1f = u5 - P["holgura"] - POSE["sY"]               # cara delantera del bloque 1
L.rect(b1f - P["largoBloque"], hx + P["hBloque2"] / 2, b1f, hy + P["hBloque1"] / 2, "pieza", 'fill="#f5cba7"')
L.texto((-50, hx), "2", "num", "middle", dy=4); L.texto((b1f - 50, hy), "1", "num", "middle", dy=4)
# placas, guías, motores
L.rect(u5, hplaca - P["altoPlaca"] / 2, u5 + e, hplaca + P["altoPlaca"] / 2, "pieza", 'fill="#aed6f1"')
L.rect(u10 - e, hplaca - P["altoPlaca"] / 2, u10, hplaca + P["altoPlaca"] / 2, "pieza", 'fill="#aed6f1"')
L.texto((u5 + 6, hplaca + 55), "5", "num", "middle", dy=-4); L.texto((u10 - 6, hplaca + 55), "10", "num", "middle", dy=-4)
for h in (hx, hy):
    L.linea((u10 - e, h), (u5 + e, h), AZUL, 3)
L.rect(u10 - e - 50, hx - 28, u10 - e, hx + 28); L.rect(u10 - e - 126, hx - 28, u10 - e - 50, hx + 28, "pieza", 'fill="#2b313b"')
L.rect(u10 - e - 50, hy + 8 - 28, u10 - e, hy + 8 + 28); L.rect(u10 - e - 126, hy + 8 - 28, u10 - e - 50, hy + 8 + 28, "pieza", 'fill="#2b313b"')
L.add(f'<text x="{L.X(u10-e-88):.1f}" y="{L.Y(hx)+4:.1f}" fill="#fff" font-size="11" text-anchor="middle">M_X</text>')
L.add(f'<text x="{L.X(u10-e-88):.1f}" y="{L.Y(hy+8)+4:.1f}" fill="#fff" font-size="11" text-anchor="middle">M_Y</text>')
# mecanismo
A, B, C, E, A2, E2 = [(PT[k]["u"], PT[k]["h"]) for k in ("A", "B", "C", "E", "A2", "E2")]
top1 = hy + P["hBloque1"] / 2
uc = C[0]
L.poli([(uc - 24.5, top1), (uc + 24.5, top1), (uc + 12, top1 + P["hC"]), (uc - 12, top1 + P["hC"])], "#fae5d3")
L.texto((uc, top1 + 50), "6", "num", "middle")
import math
phi = math.radians(F["phi"]); ua = (math.cos(phi), math.sin(phi))
p20 = (A[0] + 20 * ua[0], A[1] + 20 * ua[1]); p125 = (A[0] + 125 * ua[0], A[1] + 125 * ua[1])
L.poli([p20, p125, B], "#e8daef", MORADO)
L.texto(((p20[0] + p125[0] + B[0]) / 3, (p20[1] + p125[1] + B[1]) / 3), "8", "num", "middle")
L.linea(A, E, MORADO, 9, 'stroke-linecap="round"')
L.texto(((A[0] + E[0]) / 2, (A[1] + E[1]) / 2), "9", "num", "middle", dy=-9)
L.linea(C, B, "#d35400", 6, 'stroke-linecap="round"')
L.texto(((C[0] + B[0]) / 2, (C[1] + B[1]) / 2), "12", "num", "middle", dy=-10)
L.linea(A2, E2, VERDE, 3.5)
L.texto(((A2[0] + E2[0]) / 2, (A2[1] + E2[1]) / 2), "13", "num", "middle", dy=-8)
L.linea((A[0], hplaca + P["altoPlaca"] / 2), A2, VERDE, 4); L.linea(E, E2, VERDE, 4)
L.rect(u5 + e, A[1] - 17, A[0] + 6, A[1] + 17, "pieza", 'fill="#aed6f1"')
# pinza
L.rect(E[0] - 5, E[1] - P["pinzaBajoE"], E[0] + 75, E[1] - P["pinzaBajoE"] + P["hCuerpoPinza"], "pieza", 'fill="#d5f5e3"')
L.texto((E[0] + 40, E[1] - 20), "4", "num", "middle")
L.rect(E[0] + 75, E[1] - P["hg"] - 5, E[0] + 155, E[1] - P["hg"] + 5, "pieza", 'fill="#abebc6"')
L.texto((E[0] + 115, E[1] - P["hg"] - 10), "15", "num", "middle")
tcp = (F["r"], F["z"])
L.add(f'<path d="M{L.X(tcp[0])-6},{L.Y(tcp[1])-6} l12,12 m0,-12 l-12,12" stroke="#c0392b" stroke-width="2.2"/>')
L.texto(tcp, "TCP", "num", dx=8, dy=22)
for pnt, le, dx, dy in ((A, "A", -16, 18), (A2, "A'", -22, -6), (B, "B", 8, -8), (C, "C", -20, -8), (E, "E", -18, 18), (E2, "E'", 8, -6)):
    L.piv(pnt, le, dx, dy)

# cotas (código de la planilla)
L.cota((-r - 60, 0), (-r - 60, hx), 0, "3.1")
L.cota((-r - 110, 0), (-r - 110, hy), 0, "3.2")
L.cota((r + 15, 0), (r + 15, P["hDiscoInf"]), 0, "3.3")
L.cota((r + 15, P["hDiscoInf"]), (r + 15, h1), 0, "3.4")
L.cota((r + 15, h1), (r + 15, hc), 0, "3.5")
L.cota((-35.5, hc), (-35.5, hc + P["hColumna"]), 15, "3.7")
L.cota((0, 30), (P["largoBloque"] / 2, 30), 0, "3.9")
L.cota((-P["largoBloque"] / 2, hx - 30), (P["largoBloque"] / 2, hx - 30), 0, "4.1 (=2)", 0.5, (-75, 0))
L.cota((u10 + 22, hx), (u10 + 22, hy), 0, "4.6")
L.cota((u10, hplaca - 70), (u5, hplaca - 70), 0, "4.10", 0.3)
L.cota((P["largoBloque"] / 2, hx - 48), (u5, hx - 48), 0, "2.1 s_X", 0.5)
L.cota((b1f, top1 + 30), (u5, top1 + 30), 0, "2.2 s_Y", 0.35, (-30, 22))
L.cota((u5, A[1] - 45), (A[0], A[1] - 45), 0, "5.2")
L.cota((A[0] + 18, hx), (A[0] + 18, A[1]), 0, "5.3")
L.cota((b1f, top1 + 135), (uc, top1 + 135), 0, "5.4")
L.cota((b1f - P["largoBloque"] - 10, top1), (b1f - P["largoBloque"] - 10, C[1]), 0, "5.5")
L.cota(C, B, 22, "5.7 L12")
L.cota(A, B, 55, "5.8 a", 0.55)
L.cota(A, E, -60, "5.9 L9")
L.cota(B, E, 40, "5.10 B-E", 0.72)
L.cota(A2, E2, 22, "5.15 L13", 0.3)
L.cota((A[0] - 22, A[1]), (A[0] - 22, A2[1]), 0, "5.16", 0.5, (-28, 0))
L.cota((E[0] - 25, E[1]), (E[0] - 25, E2[1]), 0, "5.17")
L.cota((E[0], E[1] - 70), (tcp[0], E[1] - 70), 0, "6.5 d_g")
L.cota((tcp[0] + 40, tcp[1]), (tcp[0] + 40, E[1]), 0, "6.6 h_g")
L.cota((E[0] - 5, E[1] - P["pinzaBajoE"] - 18), (E[0] - 5 + 80, E[1] - P["pinzaBajoE"] - 18), 0, "6.1", 0.5)
L.cota((tcp[0] + 95, 0), (tcp[0] + 95, tcp[1]), 0, "8 z")
L.cota((0, -22), (tcp[0], -22), 0, "8 r")
# ángulo del brazo
L.add(f'<path d="M{L.X(A[0]+70):.1f},{L.Y(A[1]):.1f} A87,87 0 0 0 {L.X(A[0]+70*ua[0]):.1f},{L.Y(A[1]+70*ua[1]):.1f}" class="cota"/>')
L.linea(A, (A[0] + 85, A[1]), NARANJA, 0.8, 'stroke-dasharray="3 3"')
L.codigo(L.X(A[0] + 100), L.Y(A[1] + 10), "5.18 φ")

lateral = L.svg("Vista lateral: cotas a medir",
                f"Pose del dibujo: s_X = {POSE['sX']} mm, s_Y = {POSE['sY']} mm (desde el homing). "
                "Cada etiqueta naranja es el código de la fila de la planilla. Cotas entre centros de pasadores.")
open(os.path.join(DIR, "esquema_medidas_lateral.svg"), "w", encoding="utf-8").write(lateral)

# ======================================================================= vista superior
S = Lienzo(1280, 560, 1.25, 430, 300)          # aquí "h" es la coordenada lateral (+ = izquierda del robot)
S.add(f'<circle cx="{S.X(0)}" cy="{S.Y(0)}" r="{r*S.s}" class="pieza" fill="#e5e7e9"/>')
S.rect(-35.5, -50, 35.5, 50, "pieza", 'fill="#d5d8dc"')
S.rect(-P["largoBloque"] / 2, -P["anchoBloque"] / 2, P["largoBloque"] / 2, P["anchoBloque"] / 2, "pieza", 'fill="#cfd8dc" fill-opacity="0.6"')
S.rect(b1f - P["largoBloque"], -P["anchoBloque"] / 2, b1f, P["anchoBloque"] / 2, "pieza", 'fill="#f5cba7"')
S.rect(u5, -P["anchoPlaca"] / 2, u5 + e, P["anchoPlaca"] / 2, "pieza", 'fill="#aed6f1"')
S.rect(u10 - e, -P["anchoPlaca"] / 2, u10, P["anchoPlaca"] / 2, "pieza", 'fill="#aed6f1"')
for z in (-P["zGuias"], 0, P["zGuias"]):
    S.linea((u10 - e, z), (u5 + e, z), AZUL if z else GRIS, 4 if z else 3)
S.rect(u10 - e - 126, -28, u10 - e, 28, "pieza", 'fill="#2b313b"')
S.poli([(uc - 24.5, -17), (uc + 24.5, -17), (uc + 24.5, 17), (uc - 24.5, 17)], "#fae5d3")
# brazo, escuadra 8 (dos placas), biela, varilla al centro
Eu = E[0]
S.rect(A[0], -5, Eu, 5, "pieza", f'fill="{MORADO}" fill-opacity="0.85"')
for z0 in (-17, 6):
    S.rect(A[0] + 20 * ua[0], z0, B[0] + 12, z0 + 11, "pieza", 'fill="#e8daef" fill-opacity="0.9"')
S.rect(C[0], -5.5, B[0], 5.5, "pieza", 'fill="#d35400" fill-opacity="0.5"')
S.linea((A2[0], 0), (E2[0], 0), VERDE, 4)
S.rect(Eu - 5, -27.5, Eu + 75, 27.5, "pieza", 'fill="#d5f5e3"')
ap = math.radians(25)
for s in (1, -1):
    p0 = (Eu + 75, s * 16); p1 = (p0[0] + 80 * math.cos(ap), p0[1] + s * 80 * math.sin(ap))
    S.linea(p0, p1, "#2b313b", 7, 'stroke-linecap="round"')
S.texto((A[0] + 120, 30), "8 (dos placas)", "num"); S.texto((E2[0] - 120, -18), "13 al centro", "num")
S.texto((Eu + 50, -10), "4", "num", "middle")
S.cota((u5, -P["anchoPlaca"] / 2), (u5, P["anchoPlaca"] / 2), -25, "4.5", 0.5, (0, 95))
S.cota((u10 + 25, 0), (u10 + 25, P["zGuias"]), 0, "4.7", 0.5)
S.cota((b1f - P["largoBloque"], -P["anchoBloque"] / 2), (b1f - P["largoBloque"], P["anchoBloque"] / 2), 18, "4.2", 0.5, (-45, -80))
S.cota((-r, -r - 15), (r, -r - 15), 0, "3.6")
S.cota((-35.5, 100), (35.5, 100), 0, "3.8 (columna)", 0.5)
S.cota((A[0] + 70, -6), (A[0] + 70, 6), 0, "5.13", 0.5, (0, -55))
S.cota((Eu + 35, -27.5), (Eu + 35, 27.5), 0, "6.1", 0.5, (0, 55))
S.cota((Eu + 75, -16), (Eu + 75, 16), 0, "6.7", 0.5, (0, -60))
tips = [(Eu + 75 + 80 * math.cos(ap), s * (16 + 80 * math.sin(ap))) for s in (1, -1)]
S.cota(tips[1], tips[0], -30, "6.10", 0.5, (25, 70))
S.add(f'<line x1="{S.X(-r-20)}" y1="{S.Y(0)}" x2="{S.X(tcp[0]+40)}" y2="{S.Y(0)}" stroke="#c0392b" stroke-width="0.8" stroke-dasharray="10 4 2 4"/>')
S.texto((tcp[0] + 45, 0), "plano central", "sub", dy=18)
superior = S.svg("Vista superior: cotas a medir",
                 "La varilla 13, el brazo 9 y la biela 12 van en el plano central; la escuadra 8 son dos placas a los costados. "
                 "Garra dibujada abierta.")
open(os.path.join(DIR, "esquema_medidas_superior.svg"), "w", encoding="utf-8").write(superior)
print("esquema_medidas_lateral.svg y esquema_medidas_superior.svg")
