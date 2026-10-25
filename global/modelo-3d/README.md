# Modelo 3D del brazo XK-JS1-1

`brazo_xk-js1-1.glb` es el modelo articulado a escala real (metros, Y hacia arriba) que usa la sección
**Modelo 3D** de la página. Se genera con un script, sin Blender:

```bash
node global/modelo-3d/generar_modelo.js
```

El script toma todas las cotas de `web/js/cinematica.js`. Para corregir una medida:

1. Se cambia en `PARAMETROS`, dentro de `web/js/cinematica.js`.
2. Se vuelve a generar el modelo con el comando de arriba.
3. Se ejecuta `node semestres/2026_II/modelo-3d/cinematica/pruebas_cinematica.js`, y después
   `python3 semestres/2026_II/modelo-3d/cinematica/graficas_cinematica.py` para actualizar las figuras.

## Nodos

Cada pieza móvil tiene el origen en su eje de giro o en su guía lineal. La página solo mueve estos nodos:

| Nodo | Articulación | Valor que aplica la página |
|---|---|---|
| `base_giratoria` | revoluta, eje Y | θ base |
| `carro_x` | prismática, eje X | posición inicial + carro X |
| `carro_y` | prismática, eje X | posición inicial + carro Y |
| `biela_12` | revoluta, eje Z (pasiva) | ángulo de la biela, de la cinemática |
| `brazo_9` | revoluta, eje Z (pasiva) | φ, de la cinemática |
| `pinza` | revoluta, eje Z (pasiva) | −φ (el paralelogramo la deja horizontal) |
| `varilla_13` | revoluta, eje Z (pasiva) | φ |
| `mordaza_sup`, `mordaza_inf` | garra | ±6 mm al cerrar (Q0.7) |
| `tcp` | — | punto de trabajo (centro de las mordazas) |

La geometría es simplificada (cajas, cilindros y prismas) y las piezas sin cota usan valores **SUPUESTO**
(ver `semestres/2026_II/modelo-3d/levantamiento/levantamiento_medidas.md`).

El modelo anterior (`brazo_robotico_v2.glb`, 4.5 MB, malla generada por IA y cortada en nodos) queda fuera
del repositorio: tenía la escala aproximada y los orígenes de los nodos no estaban en los ejes.
