# Cómo aportar al repositorio

Guía para el equipo: dónde poner cada archivo y cómo hacer que aparezca bien en la [página del proyecto](https://brazo-4gdl.pages.dev/).

## 1. Dónde va cada cosa

| Qué es | Dónde va |
|---|---|
| Informe de laboratorio | `semestres/2026_II/informes/` |
| Guía de laboratorio | `semestres/2026_II/guias/` |
| Plano eléctrico (`.dwg`, `.pdf`) | `semestres/2026_II/planos/electrico/` |
| P&ID (`.dwg`, `.pdf`) | `semestres/2026_II/planos/pid/` |
| Programa del PLC (`.mwp`, `.awl`) | `semestres/2026_II/programas-plc/` |
| HMI, SCADA, comunicación | `semestres/2026_II/hmi/` |
| Base de datos (modelo, `.sql`, mockups) | `semestres/2026_II/base-de-datos/` |
| Datos de ensayos | `semestres/2026_II/pruebas/` |
| Fotos del laboratorio | `semestres/2026_II/evidencias/` |
| Medidas, cinemática e informe del modelo 3D | `semestres/2026_II/modelo-3d/` |
| Modelo 3D (`.glb`) y su generador | `global/modelo-3d/` |
| Foto de un componente de la planta | `global/fotos-planta/` (`.jpg`, máximo ~1600 px) |
| Datasheet de un componente | `global/datasheets/` |
| Manual | `global/manuales/` |
| Norma | `global/normativas/` |

Al empezar un nuevo semestre se crea su carpeta (por ejemplo `semestres/2027_I/`) y se cambia `"actual"` en `config/semestres.json`.

GitHub no guarda carpetas vacías: para crear una carpeta nueva, subir junto con el primer archivo o con un `README.md` que explique qué va ahí. Ese README se muestra en el explorador de la página.

## 2. Nombres de archivo

- **Sin tildes, sin ñ y sin espacios.** Usar `_` o `-`: `informe_2_modelado.pdf`, no `Informe 2 Modelado (final).pdf`.
- En minúsculas.
- Versiones con número, no con "final": `brazo_pid_v2.dwg`.
- La página asigna el archivo a un subsistema si el nombre o la carpeta contiene:

  | Subsistema | Palabras |
  |---|---|
  | Ejes X-Y | `motor_xy`, `eje_x`, `eje_y`, `final_de_carrera` |
  | Eje Z | `motor_z`, `eje_z`, `sensor_inductivo` |
  | Garra | `garra`, `efector`, `solenoide` |
  | Potencia y mando | `driver`, `fuente`, `disyuntor`, `rele_`, `botonera` |
  | PLC S7-200 | `plc`, `s7-200`, `map_serv`, y los `.mwp` / `.awl` |
  | Datos y HMI | `base-de-datos`, `hmi`, `interfaz`, `mockup`, `scada`, `.sql` |

- Y lo clasifica por la carpeta y el nombre: `guia` → Guías, carpeta `electrico` → Planos eléctricos, carpeta `pid` o `p&id` en el nombre → P&ID, `mockup` → Mockups.

## 3. Subir archivos

**Desde la web de GitHub** (lo más simple):

1. Entrar a la carpeta en GitHub.
2. **Add file → Upload files**, arrastrar los archivos.
3. Escribir un mensaje que diga qué se sube (`Informe 2 de laboratorio`) y **Commit changes** en `main`.

**Desde la terminal:**

```bash
git pull
git add semestres/2026_II/informes/informe_2_modelado.pdf
git commit -m "Informe 2: modelado del brazo"
git push
```

Siempre hacer `git pull` antes de empezar, para no pisar el trabajo de otros.

La página se actualiza sola en uno o dos minutos (el estado del despliegue de Cloudflare aparece junto al commit en GitHub).

## 4. Títulos y descripciones (`config/archivos.json`)

Sin configurar nada, la página usa el nombre del archivo como título. Para ponerle un título y una descripción:

```json
"semestres/2026_II/informes/informe_2_modelado.pdf": {
  "titulo": "Informe 2 - Modelado del brazo",
  "descripcion": "Cinemática directa e inversa y función de transferencia de los ejes.",
  "subsistemas": [1, 2]
}
```

- `subsistemas`: 1 Ejes X-Y, 2 Eje Z, 3 Garra, 4 Potencia y mando, 5 PLC S7-200, 6 Datos y HMI.
- Una clave que termina en `/` se aplica a todos los archivos de esa carpeta.
- `"categoria"` fuerza la categoría: `guia`, `informe`, `pid`, `electrico`, `plano`, `mockup`, `diagrama`, `modelo3d`, `datasheet`, `manual`, `normativa`, `plantilla`, `presentacion`, `datos`, `programa`, `basedatos`.
- `"oculto": true` lo saca de las listas (sigue en el explorador de carpetas).
- `"orden"`: un número menor aparece primero.

Cuidado con las comas: si el JSON queda mal escrito, la página no se actualiza y el error aparece en el registro del despliegue en Cloudflare (y junto al commit en GitHub). Se puede revisar en https://jsonlint.com.

## 5. Videos (`config/videos.json`)

Los videos pesan demasiado para el repositorio (GitHub rechaza archivos de más de 100 MB). Subirlos a YouTube como **no listados** y agregarlos así:

```json
{
  "videos": [
    {
      "titulo": "Prueba de referencia del eje Z",
      "url": "https://www.youtube.com/watch?v=XXXXXXXXXXX",
      "semestre": "2026_II",
      "subsistemas": [2]
    }
  ]
}
```

## 6. Cinemática y modelo 3D

Las medidas del brazo y la cinemática están en un solo archivo: `web/js/cinematica.js` (bloque `PARAMETROS`).
Los valores marcados `SUPUESTO` todavía no se midieron en la planta. Al cambiar uno, actualizar lo que
depende de él:

```bash
node global/modelo-3d/generar_modelo.js                          # modelo 3D (.glb)
node semestres/2026_II/modelo-3d/cinematica/pruebas_cinematica.js  # pruebas, parametros.json y tabla
python3 semestres/2026_II/modelo-3d/cinematica/graficas_cinematica.py  # figuras del informe
```

- No editar a mano `brazo_xk-js1-1.glb` ni `parametros.json`: se generan.
- Si una medida deja de ser `SUPUESTO`, poner en el comentario de dónde sale (boceto, foto o medición) y
  quitarla de la lista `SUPUESTOS` del mismo archivo.
- Las librerías externas de la página se cargan solo desde CDN y con versión fija (por ejemplo
  `three@0.160.0`).

## 7. Semestres y equipo (`config/semestres.json`)

Ahí va el resumen de cada semestre, el docente y los integrantes de cada grupo. Se muestran en la página y conviene actualizarlo al empezar cada gestión.
