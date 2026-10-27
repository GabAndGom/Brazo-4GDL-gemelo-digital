#!/usr/bin/env python3
"""Arma la interfaz de la app (carpeta ui/) con lo justo del repositorio y, si se pide,
exporta la app autónoma a otra carpeta y a un .zip.

    python3 empaquetar.py                                  # actualiza ui/ desde el repo
    python3 empaquetar.py --destino ~/gemelo_brazo_app     # además copia la app allí (+ .zip)

Copia: web/js/cinematica.js, web/js/conexion-plc.js, web/js/modelo3d.js, web/css/estilos.css,
global/modelo-3d/brazo_xk-js1-1.glb y parametros.json. La sección "Modelo 3D" de index.html
se inserta en plantilla.html: así la ventana de la app y la página usan los mismos controles.
"""
import argparse
import os
import re
import shutil

APP = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(APP, '..', '..', '..', '..'))
UI = os.path.join(APP, 'ui')

COPIAS = {
    'web/js/cinematica.js': 'ui/js/cinematica.js',
    'web/js/conexion-plc.js': 'ui/js/conexion-plc.js',
    'web/js/modelo3d.js': 'ui/js/modelo3d.js',
    'web/css/estilos.css': 'ui/css/estilos.css',
    'global/modelo-3d/brazo_xk-js1-1.glb': 'ui/modelo/brazo_xk-js1-1.glb',
    'web/img/favicon.svg': 'ui/icono.svg',
    'semestres/2026_II/modelo-3d/cinematica/parametros.json': 'parametros.json',
}
# Se conservan al volver a exportar (y nunca se copian desde el repositorio)
DATOS_PLANTA = ['calibracion.json', 'registro_gemelo.log', 'usuarios.json', 'tls_certificado.pem', 'tls_clave.pem']
EXCLUIR = {'__pycache__', '_prueba_calibracion.json'} | set(DATOS_PLANTA)


def actualizar_ui():
    for origen, destino in COPIAS.items():
        d = os.path.join(APP, destino)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(os.path.join(REPO, origen), d)
    with open(os.path.join(REPO, 'index.html'), encoding='utf-8') as f:
        html = f.read()
    m = re.search(r'    <!-- MODELO 3D -->\n(.*?)\n    <!-- SUBSISTEMAS -->', html, re.S)
    if not m:
        raise SystemExit('no se encontró la sección Modelo 3D en index.html')
    seccion = m.group(1)
    # Los botones que abren documentos del repositorio no existen en la app
    seccion = re.sub(r'\s*<button class="enlace-boton" data-ver="[^"]*">[^<]*</button>', '', seccion)
    # En la app el modo por defecto es el brazo real
    seccion = seccion.replace('<option value="simulacion">Simulación</option>\n                  <option value="planta">',
                              '<option value="simulacion">Simulación (sin PLC)</option>\n                  <option value="planta" selected>')
    with open(os.path.join(APP, 'plantilla.html'), encoding='utf-8') as f:
        plantilla = f.read()
    with open(os.path.join(UI, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(plantilla.replace('{{MODELO3D}}', seccion))
    print('ui/ actualizada desde', REPO)


def exportar(destino):
    destino = os.path.abspath(os.path.expanduser(destino))
    guardados = {}
    for n in DATOS_PLANTA:
        p = os.path.join(destino, n)
        if os.path.exists(p):
            with open(p, 'rb') as f:
                guardados[n] = f.read()
    if os.path.exists(destino):
        shutil.rmtree(destino)
    shutil.copytree(APP, destino, ignore=lambda d, nombres: [n for n in nombres if n in EXCLUIR])
    for n, contenido in guardados.items():
        with open(os.path.join(destino, n), 'wb') as f:
            f.write(contenido)
    archivo = shutil.make_archive(destino, 'zip', os.path.dirname(destino), os.path.basename(destino))
    print('app exportada en', destino, 'y', archivo)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--destino', help='carpeta donde dejar la app autónoma (se reemplaza)')
    a = ap.parse_args()
    actualizar_ui()
    if a.destino:
        exportar(a.destino)
