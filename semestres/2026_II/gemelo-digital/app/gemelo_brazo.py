#!/usr/bin/env python3
"""Aplicación del gemelo digital del brazo XK-JS1-1.

Conecta con el PLC S7-200 por el cable USB-PPI y abre una ventana con el visor 3D, que sigue
al brazo real. Desde la ventana se puede además mandar el brazo, si el programa del PLC lo
permite y el mando está habilitado.

Uso:
    python3 gemelo_brazo.py                    # busca el PLC en /dev/ttyUSB0 y abre la ventana
    python3 gemelo_brazo.py --direccion 6      # sin búsqueda
    python3 gemelo_brazo.py --simulado         # sin PLC (para practicar)
    python3 gemelo_brazo.py --navegador        # en el navegador en vez de la ventana

La interfaz también queda en http://localhost:8050/ para abrirla desde otro navegador.
"""
import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brazo import UI, Brazo  # noqa: E402
import ventana  # noqa: E402

BRAZO = None


class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=UI, **k)

    def log_message(self, formato, *args):
        if self.path.startswith('/api/') and self.command == 'GET':
            return                                   # las lecturas periódicas no se registran
        sys.stderr.write('%s %s\n' % (self.address_string(), formato % args))

    def end_headers(self):
        # La página publicada (https) también puede conectarse a esta app en localhost
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        if self.path.startswith('/api/'):
            self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def _json(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/info':
            return self._json(200, BRAZO.info())
        if self.path == '/api/estado':
            return self._json(200, BRAZO.leer_estado())
        if not self.path.startswith('/api/'):
            return super().do_GET()
        self._json(404, {'ok': False, 'error': 'ruta desconocida'})

    def do_POST(self):
        try:
            n = int(self.headers.get('Content-Length') or 0)
            datos = json.loads(self.rfile.read(n) or b'{}') if n else {}
            ruta = self.path.split('?')[0]
            if ruta == '/api/mando':
                BRAZO.habilitar_mando(bool(datos.get('habilitado')))
                return self._json(200, {'ok': True, 'mando': BRAZO.mando})
            if ruta == '/api/calibrar_base':
                return self._json(200, BRAZO.calibrar_base(datos.get('angulo')))
            if ruta.startswith('/api/orden/'):
                r = BRAZO.orden(ruta.rsplit('/', 1)[1], datos)
                return self._json(200, r or {'ok': True})
            self._json(404, {'ok': False, 'error': 'ruta desconocida'})
        except (ValueError, KeyError) as ex:
            self._json(400, {'ok': False, 'error': str(ex)})
        except Exception as ex:                       # error de comunicación u otro
            self._json(500, {'ok': False, 'error': str(ex)})


def main():
    global BRAZO
    ap = argparse.ArgumentParser(description='Gemelo digital del brazo XK-JS1-1 (PLC S7-200 por PPI)')
    ap.add_argument('--puerto', default='/dev/ttyUSB0', help='puerto serie del cable USB-PPI')
    ap.add_argument('--direccion', type=int, default=None, help='dirección PPI del PLC (por defecto la busca)')
    ap.add_argument('--simulado', action='store_true', help='usar un PLC simulado (sin hardware)')
    ap.add_argument('--http', type=int, default=8050, help='puerto de la página (por defecto 8050)')
    ap.add_argument('--navegador', action='store_true', help='abrir en el navegador en vez de la ventana')
    ap.add_argument('--sin-ventana', action='store_true', help='solo el servidor (sin ventana ni navegador)')
    a = ap.parse_args()

    registro = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'registro_gemelo.log')
    BRAZO = Brazo(a.puerto, a.direccion, a.simulado, registro)
    srv = ThreadingHTTPServer(('127.0.0.1', a.http), Manejador)
    url = f'http://localhost:{a.http}/'
    print(f'Gemelo digital en {url}  (cierre la ventana o Ctrl+C para salir)', flush=True)

    def detener_brazo():
        if BRAZO.conectado and BRAZO.mando and BRAZO.leer_estado().get('en_movimiento'):
            try:
                BRAZO.orden('detener', {})
            except Exception:
                pass

    try:
        if not a.navegador and not a.sin_ventana and ventana.disponible():
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            ventana.abrir(url, detener_brazo)
        else:
            if not a.sin_ventana:
                threading.Timer(1.0, lambda: webbrowser.open(url)).start()
            srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        detener_brazo()
        srv.server_close()
        print('\nApp cerrada.')


if __name__ == '__main__':
    main()
