#!/usr/bin/env python3
"""Aplicación del gemelo digital del brazo XK-JS1-1.

Conecta con el PLC S7-200 por el cable USB-PPI y abre una ventana con el visor 3D, que sigue
al brazo real. Desde la ventana se puede además mandar el brazo, si el programa del PLC lo
permite y el mando está habilitado.

Uso:
    python3 gemelo_brazo.py                    # busca el PLC en /dev/ttyUSB0 y abre la ventana
    python3 gemelo_brazo.py --red              # además, acceso con usuario y contraseña desde la red local
    python3 gemelo_brazo.py --direccion 6      # sin búsqueda
    python3 gemelo_brazo.py --simulado         # sin PLC (para practicar)
    python3 gemelo_brazo.py --navegador        # en el navegador en vez de la ventana

La ventana de esta PC usa http://localhost:8050/ (sin contraseña: quien está aquí está en la planta).
Con --red, los demás dispositivos entran por https://IP-DE-ESTA-PC:8443/ con su usuario
(los usuarios se crean con usuarios.py).
"""
import argparse
import html
import json
import os
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brazo import APP, UI, Brazo  # noqa: E402
import acceso  # noqa: E402
import ventana  # noqa: E402

BRAZO = None
ACCESO = acceso.Acceso()
CLAVE_LOCAL = False                 # --clave-local: pedir contraseña también en esta PC
COOKIE = 'gemelo_sesion'
SOLO_OPERADOR = ('/api/mando', '/api/calibrar_base')
PUBLICOS = ('/login', '/icono.svg')

PAGINA_LOGIN = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Gemelo digital · Ingreso</title>
<link rel="icon" href="icono.svg"><style>
:root{color-scheme:light dark;--acento:#c2620c}
body{margin:0;min-height:100vh;display:grid;place-items:center;font-family:system-ui,sans-serif;
background:#1b1916;color:#eee}
form{background:#26231f;padding:28px 26px;border-radius:8px;border-top:4px solid var(--acento);width:min(340px,90vw);
display:grid;gap:12px;box-shadow:0 10px 30px rgba(0,0,0,.4)}
h1{font-size:18px;margin:0}small{color:#aaa}label{display:grid;gap:4px;font-size:13px}
input{font:inherit;padding:9px 10px;border-radius:5px;border:1px solid #555;background:#141210;color:#eee}
button{font:inherit;padding:10px;border:0;border-radius:5px;background:var(--acento);color:#fff;font-weight:600;cursor:pointer}
.error{color:#ff9a8f;font-size:13px;min-height:1em}
</style></head><body><form method="post" action="login">
<h1>Gemelo digital · Brazo XK-JS1-1</h1><small>Ingrese con su usuario del laboratorio</small>
<label>Usuario <input name="usuario" autocomplete="username" required autofocus></label>
<label>Contraseña <input name="clave" type="password" autocomplete="current-password" required></label>
<div class="error">{error}</div><button>Entrar</button>
<small>Observador: solo ve el brazo. Operador: lo manda (siempre con alguien en la planta).</small>
</form></body></html>"""


class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=UI, **k)

    def log_message(self, formato, *args):
        if self.path.startswith('/api/') and self.command == 'GET':
            return                                   # las lecturas periódicas no se registran
        sys.stderr.write('%s %s\n' % (self.address_string(), formato % args))

    # -------------------------------------------------------------- sesión
    @property
    def local(self):
        return self.client_address[0] in ('127.0.0.1', '::1') and not getattr(self.server, 'tls', False) \
            and not CLAVE_LOCAL

    def _token(self):
        for parte in (self.headers.get('Cookie') or '').split(';'):
            k, _, v = parte.strip().partition('=')
            if k == COOKIE:
                return v
        return None

    def sesion(self):
        if self.local:
            return {'usuario': 'local', 'rol': 'operador'}
        return ACCESO.sesion(self._token())

    def _mismo_origen(self):
        """Protección contra páginas ajenas: las órdenes deben venir de esta misma app."""
        origen = self.headers.get('Origin')
        if origen is None:
            return self.local                         # curl en esta PC
        esquema = 'https' if getattr(self.server, 'tls', False) else 'http'
        return origen == f'{esquema}://{self.headers.get("Host")}'

    # -------------------------------------------------------------- respuestas
    def end_headers(self):
        # Otras páginas abiertas en esta PC (por ejemplo la publicada) pueden LEER el estado
        if self.local and self.command in ('GET', 'OPTIONS'):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
        if self.path.startswith('/api/') or self.path in ('/', '/index.html', '/login'):
            self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Frame-Options', 'DENY')
        super().end_headers()

    def _json(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _html(self, codigo, texto, cabeceras=()):
        cuerpo = texto.encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(cuerpo)))
        for k, v in cabeceras:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _ir(self, destino, cabeceras=()):
        self.send_response(303)
        self.send_header('Location', destino)
        for k, v in cabeceras:
            self.send_header(k, v)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _cookie(self, valor, segundos):
        seguro = '; Secure' if getattr(self.server, 'tls', False) else ''
        return ('Set-Cookie', f'{COOKIE}={valor}; Path=/; HttpOnly; SameSite=Strict; Max-Age={segundos}{seguro}')

    def _index(self, s):
        with open(os.path.join(UI, 'index.html'), encoding='utf-8') as f:
            pagina = f.read()
        # El rol decide si la página puede mandar el brazo real (el servidor lo vuelve a comprobar)
        datos = json.dumps({'usuario': s['usuario'], 'rol': s['rol'], 'local': self.local})
        pagina = pagina.replace('window.GEMELO_CONTROL = true;',
                                f'window.GEMELO_CONTROL = {json.dumps(s["rol"] == "operador")}; '
                                f'window.GEMELO_USUARIO = {datos};')
        self._html(200, pagina)

    # -------------------------------------------------------------- GET / POST
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.end_headers()

    def do_GET(self):
        ruta = self.path.split('?')[0]
        if ruta == '/login':
            return self._html(200, PAGINA_LOGIN.replace('{error}', ''))
        if ruta == '/salir':
            s = ACCESO.salir(self._token())
            if s:
                BRAZO.soltar_mando_de(s['usuario'])
            return self._ir('login', [self._cookie('', 0)])
        s = self.sesion()
        if ruta.startswith('/api/'):
            if not s:
                return self._json(401, {'ok': False, 'error': 'sesión vencida: vuelva a ingresar'})
            if ruta == '/api/info':
                return self._json(200, BRAZO.info())
            if ruta == '/api/estado':
                return self._json(200, BRAZO.leer_estado())
            if ruta == '/api/sesion':
                return self._json(200, {'usuario': s['usuario'], 'rol': s['rol'], 'local': self.local,
                                        'conectados': ACCESO.activas()})
            return self._json(404, {'ok': False, 'error': 'ruta desconocida'})
        if ruta in ('/', '/index.html'):
            return self._index(s) if s else self._ir('login')
        if not s and ruta not in PUBLICOS and not ruta.startswith(('/css/', '/lib/', '/js/', '/modelo/')):
            return self._ir('login')
        return super().do_GET()

    def do_POST(self):
        ruta = self.path.split('?')[0]
        n = min(int(self.headers.get('Content-Length') or 0), 65536)
        cuerpo = self.rfile.read(n) if n else b''
        if ruta == '/login':
            campos = urllib.parse.parse_qs(cuerpo.decode('utf-8', 'replace'))
            usuario = (campos.get('usuario') or [''])[0].strip()
            try:
                token, rol = ACCESO.entrar(usuario, (campos.get('clave') or [''])[0], self.client_address[0])
            except ValueError as ex:
                BRAZO._log(f'ingreso fallido de "{usuario}" desde {self.client_address[0]}')
                return self._html(401, PAGINA_LOGIN.replace('{error}', html.escape(str(ex))))
            BRAZO._log(f'ingreso de {usuario} ({rol}) desde {self.client_address[0]}')
            return self._ir('./', [self._cookie(token, acceso.DURACION)])
        s = self.sesion()
        if not s:
            return self._json(401, {'ok': False, 'error': 'sesión vencida: vuelva a ingresar'})
        if not self._mismo_origen():
            return self._json(403, {'ok': False, 'error': 'solo lectura: las órdenes se dan desde la app del gemelo'})
        if s['rol'] != 'operador' and (ruta in SOLO_OPERADOR or ruta.startswith('/api/orden/')):
            BRAZO._log(f'RECHAZADO {ruta} de {s["usuario"]} ({s["rol"]}): solo puede ver')
            return self._json(403, {'ok': False, 'error': 'su usuario es observador: solo puede ver el brazo'})
        try:
            datos = json.loads(cuerpo or b'{}')
            quien = s['usuario']
            if ruta == '/api/mando':
                BRAZO.habilitar_mando(bool(datos.get('habilitado')), quien)
                return self._json(200, {'ok': True, 'mando': BRAZO.mando, 'mando_de': BRAZO.mando_de})
            if ruta == '/api/calibrar_base':
                return self._json(200, BRAZO.calibrar_base(datos.get('angulo')))
            if ruta.startswith('/api/orden/'):
                r = BRAZO.orden(ruta.rsplit('/', 1)[1], datos, quien)
                return self._json(200, r or {'ok': True})
            self._json(404, {'ok': False, 'error': 'ruta desconocida'})
        except (ValueError, KeyError) as ex:
            BRAZO._log(f'RECHAZADO {ruta} de {s["usuario"]}: {ex}')
            self._json(400, {'ok': False, 'error': str(ex)})
        except Exception as ex:                       # error de comunicación u otro
            self._json(500, {'ok': False, 'error': str(ex)})


def certificado():
    """Certificado TLS propio (autofirmado) para el acceso por red; se crea una sola vez."""
    cert, clave = os.path.join(APP, 'tls_certificado.pem'), os.path.join(APP, 'tls_clave.pem')
    if not (os.path.exists(cert) and os.path.exists(clave)):
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '3650',
                        '-subj', '/CN=gemelo-brazo-xk-js1-1', '-keyout', clave, '-out', cert],
                       check=True, capture_output=True)
        os.chmod(clave, 0o600)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, clave)
    return ctx


def ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))       # no envía nada: solo elige la interfaz de salida
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return '127.0.0.1'


def vigilar_mando():
    """Si quien tiene el mando ya no tiene sesión (salió o venció), el mando se suelta."""
    while True:
        time.sleep(15)
        quien = BRAZO.mando_de
        if BRAZO.mando and quien not in (None, 'local') and quien not in {u for u, _ in ACCESO.activas()}:
            BRAZO.soltar_mando_de(quien)


def main():
    global BRAZO, CLAVE_LOCAL
    ap = argparse.ArgumentParser(description='Gemelo digital del brazo XK-JS1-1 (PLC S7-200 por PPI)')
    ap.add_argument('--puerto', default='/dev/ttyUSB0', help='puerto serie del cable USB-PPI')
    ap.add_argument('--direccion', type=int, default=None, help='dirección PPI del PLC (por defecto la busca)')
    ap.add_argument('--simulado', action='store_true', help='usar un PLC simulado (sin hardware)')
    ap.add_argument('--http', type=int, default=8050, help='puerto local de la ventana (por defecto 8050)')
    ap.add_argument('--red', action='store_true', help='acceso con usuario y contraseña desde la red local')
    ap.add_argument('--puerto-red', type=int, default=8443, help='puerto del acceso por red (por defecto 8443)')
    ap.add_argument('--sin-cifrado', action='store_true', help='red local por http (las contraseñas viajan en claro)')
    ap.add_argument('--clave-local', action='store_true', help='pedir contraseña también en esta PC')
    ap.add_argument('--navegador', action='store_true', help='abrir en el navegador en vez de la ventana')
    ap.add_argument('--sin-ventana', action='store_true', help='solo el servidor (sin ventana ni navegador)')
    a = ap.parse_args()
    CLAVE_LOCAL = a.clave_local

    if (a.red or a.clave_local) and not ACCESO.hay_usuarios():
        raise SystemExit('No hay usuarios. Cree al menos uno antes:\n'
                         '  python3 usuarios.py agregar NOMBRE --rol operador')

    registro = os.path.join(APP, 'registro_gemelo.log')
    BRAZO = Brazo(a.puerto, a.direccion, a.simulado, registro)
    servidores = [ThreadingHTTPServer(('127.0.0.1', a.http), Manejador)]
    url = f'http://localhost:{a.http}/'
    print(f'Gemelo digital en {url}  (cierre la ventana o Ctrl+C para salir)', flush=True)
    if a.red:
        red = ThreadingHTTPServer(('0.0.0.0', a.puerto_red), Manejador)
        red.tls = not a.sin_cifrado
        if red.tls:
            red.socket = certificado().wrap_socket(red.socket, server_side=True)
        esquema = 'https' if red.tls else 'http'
        servidores.append(red)
        BRAZO._log(f'acceso por red local: {esquema}://{ip_local()}:{a.puerto_red}/ (con usuario y contraseña)')
        if red.tls:
            print('  El certificado es propio del laboratorio: la primera vez el navegador avisa;'
                  ' acepte continuar a ese sitio.', flush=True)
        threading.Thread(target=vigilar_mando, daemon=True).start()
    for srv in servidores[1:]:
        threading.Thread(target=srv.serve_forever, daemon=True).start()

    def detener_brazo():
        if BRAZO.conectado and BRAZO.mando and BRAZO.leer_estado().get('en_movimiento'):
            try:
                BRAZO.orden('detener', {}, BRAZO.mando_de or 'local')
            except Exception:
                pass

    principal = servidores[0]
    try:
        if not a.navegador and not a.sin_ventana and ventana.disponible():
            threading.Thread(target=principal.serve_forever, daemon=True).start()
            ventana.abrir(url, detener_brazo)
        else:
            if not a.sin_ventana:
                threading.Timer(1.0, lambda: webbrowser.open(url)).start()
            principal.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        detener_brazo()
        for srv in servidores:
            srv.server_close()
        print('\nApp cerrada.')


if __name__ == '__main__':
    main()
