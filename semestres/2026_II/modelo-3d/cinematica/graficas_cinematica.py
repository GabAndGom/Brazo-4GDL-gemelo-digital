"""
Gráficas de la cinemática del brazo XK-JS1-1 para el informe.

    node semestres/2026_II/modelo-3d/cinematica/pruebas_cinematica.js   (genera parametros.json)
    python3 semestres/2026_II/modelo-3d/cinematica/graficas_cinematica.py

Lee parametros.json (fuente: web/js/cinematica.js), vuelve a implementar la
cinemática directa en Python, la compara con tabla_cinematica.csv (generada por
el módulo JavaScript) y guarda las figuras en ../informe/figuras/.
Requiere numpy y matplotlib.
"""
import csv
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DIR = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(DIR, "..", "informe", "figuras")
os.makedirs(FIG, exist_ok=True)

with open(os.path.join(DIR, "parametros.json"), encoding="utf-8") as f:
    datos = json.load(f)
P, D = datos["parametros"], datos["derivados"]
BETA = np.radians(P["beta"])

plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.3, "figure.dpi": 150})
NARANJA, AZUL, GRIS = "#c2620c", "#2f7fc1", "#8a8f98"


def psi_de(sY):
    """Ángulo de A-B (rad) para la carrera sY: cierre del lazo A-B-C."""
    cx, cz = sY + D["cu0"], D["ch"]
    dist = np.hypot(cx, cz)
    cosg = (P["a"] ** 2 + dist ** 2 - P["L12"] ** 2) / (2 * P["a"] * dist)
    return np.arctan2(cz, cx) - np.arccos(cosg)


def directa(theta, sX, sY):
    """Devuelve dict con phi [°], r, z, X, Y, Z [mm] y puntos A, B, C, E del plano."""
    sX, sY = np.broadcast_arrays(np.asarray(sX, float), np.asarray(sY, float))
    psi = psi_de(sY)
    phi = psi - BETA
    uA = D["u5_0"] + sX + P["uA"]
    A = (uA, D["hA"])
    B = (uA + P["a"] * np.cos(psi), D["hA"] + P["a"] * np.sin(psi))
    C = (uA + sY + D["cu0"], D["hCabs"])
    E = (uA + P["L9"] * np.cos(phi), D["hA"] + P["L9"] * np.sin(phi))
    r, z = E[0] + P["dg"], E[1] - P["hg"]
    th = np.radians(theta)
    return dict(phi=np.degrees(phi), r=r, z=z, X=r * np.cos(th), Y=r * np.sin(th), Z=z, A=A, B=B, C=C, E=E)


def dphi_num(sY, h=1e-4):
    return (np.degrees(psi_de(sY + h)) - np.degrees(psi_de(sY - h))) / (2 * h)


# ---------------------------------------------------------------- validación cruzada JS vs Python
err = 0.0
with open(os.path.join(DIR, "tabla_cinematica.csv"), encoding="utf-8") as f:
    for fila in csv.DictReader(f):
        k = directa(0, float(fila["sX_mm"]), float(fila["sY_mm"]))
        err = max(err, abs(k["r"] - float(fila["r_mm"])), abs(k["z"] - float(fila["z_mm"])))
print(f"Validación cruzada JavaScript vs Python: diferencia máxima {err:.3f} mm (redondeo a 0.1 mm)")

RX, RY = P["recorridoX"], P["recorridoY"]
sx = np.linspace(0, RX, 61)
sy = np.linspace(0, RY, 61)
SX, SY = np.meshgrid(sx, sy)
K = directa(0, SX, SY)

# ---------------------------------------------------------------- 1. corte r-z
fig, ax = plt.subplots(figsize=(6.4, 4.2))
ax.scatter(K["r"].ravel(), K["z"].ravel(), s=2, color=NARANJA, alpha=0.35, label="combinaciones de carreras")
for s, est, lab in [(0, "-", "carro Y = 0 (brazo arriba)"), (RY, "--", f"carro Y = {RY:g} mm (brazo abajo)")]:
    k = directa(0, sx, s)
    ax.plot(k["r"], k["z"], est, color=AZUL, lw=1.5, label=lab)
for s, lab in [(0, "carro X = 0"), (RX, f"carro X = {RX:g} mm")]:
    k = directa(0, s, sy)
    ax.plot(k["r"], k["z"], color="k", lw=1)
    ax.annotate(lab, (k["r"][len(sy) // 2], k["z"][len(sy) // 2]), fontsize=8, xytext=(4, 0), textcoords="offset points")
ax.axhline(0, color=GRIS, lw=2)
ax.text(5, 6, "mesa", color=GRIS, fontsize=8)
ax.set_xlabel("r: alcance radial del TCP [mm]")
ax.set_ylabel("z: altura del TCP sobre la mesa [mm]")
ax.set_title("Espacio de trabajo: corte r-z (θ base = cualquiera)")
ax.set_aspect("equal")
ax.set_xlim(0, K["r"].max() + 40)
ax.set_ylim(-20, K["z"].max() + 60)
ax.legend(fontsize=7, loc="upper left")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "espacio_trabajo_rz.png"))

# ---------------------------------------------------------------- 2. vista superior
fig, ax = plt.subplots(figsize=(5.2, 5.2))
rmin, rmax = K["r"].min(), K["r"].max()
t = np.radians(np.linspace(P["thetaMin"], P["thetaMax"], 300))
ax.fill(np.concatenate([rmax * np.cos(t), rmin * np.cos(t[::-1])]),
        np.concatenate([rmax * np.sin(t), rmin * np.sin(t[::-1])]), color=NARANJA, alpha=0.3, label="alcance del TCP")
ax.add_patch(plt.Circle((0, 0), P["rDisco"], color=GRIS, alpha=0.5, label="base Ø165"))
ax.plot([0, rmax * 1.05], [0, 0], color=AZUL, lw=1, ls="--")
ax.text(rmax * 0.55, 12, "θ = 0 (sensor inductivo)", color=AZUL, fontsize=8)
ax.text(-rmax * 0.95, -rmax * 0.95, f"θ ∈ [{P['thetaMin']:g}°, {P['thetaMax']:g}°] (SUPUESTO)", fontsize=8)
ax.set_aspect("equal")
ax.set_xlabel("X [mm]")
ax.set_ylabel("Y [mm]")
ax.set_title(f"Vista superior: corona r ∈ [{rmin:.0f}, {rmax:.0f}] mm")
ax.legend(fontsize=8, loc="upper right")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "espacio_trabajo_superior.png"))

# ---------------------------------------------------------------- 3. φ(sY) y sensibilidad
k = directa(0, 0, sy)
fig, ax1 = plt.subplots(figsize=(6.4, 3.6))
ax1.plot(sy, k["phi"], color=NARANJA, lw=2)
ax1.set_xlabel("carrera del carro Y, sY [mm]")
ax1.set_ylabel("φ: ángulo del brazo 9 [°]", color=NARANJA)
ax2 = ax1.twinx()
ax2.plot(sy, [dphi_num(s) for s in sy], color=AZUL, lw=1.5, ls="--")
ax2.set_ylabel("dφ/dsY [°/mm]", color=AZUL)
ax2.grid(False)
ax1.set_title("Relación carro Y → ángulo del brazo (mecanismo biela-manivela)")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "phi_vs_carro_y.png"))

# ---------------------------------------------------------------- 4. posturas del mecanismo
fig, ax = plt.subplots(figsize=(6.6, 4.2))
for s, col in [(0, AZUL), (RY / 2, GRIS), (RY, NARANJA)]:
    k = directa(0, 60, s)
    A, B, C, E = k["A"], k["B"], k["C"], k["E"]
    ax.plot([C[0], B[0]], [C[1], B[1]], color=col, lw=2)                 # biela 12
    ax.plot([A[0], B[0], E[0]], [A[1], B[1], E[1]], color=col, lw=1, ls=":")
    ax.plot([A[0], E[0]], [A[1], E[1]], color=col, lw=3)                 # brazo 9
    ax.plot([E[0], k["r"]], [E[1] - P["hg"], k["z"]], color=col, lw=1)
    ax.plot(k["r"], k["z"], "x", color=col, ms=7)
    ax.plot(*zip(A, B, C, E), "o", color=col, mfc="white", ms=4)
    ax.annotate(f"sY = {s:g}", C, fontsize=8, color=col, xytext=(-30, 6), textcoords="offset points")
ax.axhline(0, color=GRIS, lw=2)
ax.set_aspect("equal")
ax.set_xlabel("r [mm]")
ax.set_ylabel("z [mm]")
ax.set_title("Posturas del mecanismo con carro X = 60 mm")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "posturas_mecanismo.png"))

# ---------------------------------------------------------------- 5. pulsos
T = datos["transmision"]
print(f"Resolución: {T['mmPorPulso']} mm/pulso en X e Y, {T['gradosPorPulso']} °/pulso en la base")
print(f"Figuras en {os.path.normpath(FIG)}")
