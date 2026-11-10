#!/usr/bin/env python3
"""Aplicación del gemelo digital del brazo XK-JS1-1 (Linux y Windows).

Una sola app con un menú de inicio que ofrece tres modos:

  Simulación          PLC simulado en la propia app: para practicar sin brazo ni cable.
  Operación local     brazo real por el cable USB-PPI, mandado desde esta PC.
  Operación por red   lo mismo, y además celulares y otras PC de la red local entran con
                      usuario y contraseña por https://IP-DE-ESTA-PC:8443/

El menú también administra los usuarios del acceso por red. Se puede cambiar de modo en
cualquier momento con el botón «Menú» de la barra superior.

Uso:
    python3 gemelo_brazo.py                    # abre el menú (Windows: py gemelo_brazo.py)
    python3 gemelo_brazo.py --modo local       # entra directo a un modo: simulacion, local o red
    python3 gemelo_brazo.py --modo red --red-simulado   # acceso por red con el PLC simulado
    python3 gemelo_brazo.py --puerto COM4      # fijar el puerto del cable (por defecto lo busca)
    python3 gemelo_brazo.py --navegador        # en el navegador en vez de la ventana propia

La ventana de esta PC usa http://localhost:8050/ (sin contraseña: quien está aquí está en la planta).
"""
import argparse
import html
import json
import os
import re
import socket
import ssl
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

for _s in (sys.stdout, sys.stderr):            # la consola de Windows no siempre admite «…» o tildes
    try:
        _s.reconfigure(errors='replace')
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brazo import APP, UI, Brazo  # noqa: E402
import acceso  # noqa: E402
import certificado_tls  # noqa: E402
import qr  # noqa: E402
import serie  # noqa: E402
import ventana  # noqa: E402

BRAZO = None                        # conexión con el PLC (real o simulado) del modo elegido
ACCESO = acceso.Acceso()
CLAVE_LOCAL = False                 # --clave-local: pedir contraseña también en esta PC
COOKIE = 'gemelo_sesion'
SOLO_OPERADOR = ('/api/mando', '/api/calibrar_base')
PUBLICOS = ('/login', '/icono.svg', '/manifest.webmanifest', '/sw.js', '/icono-192.png', '/icono-512.png',
            '/icono-maskable.png')
URL_PAGINA = 'https://brazo-4gdl-gemelo-digital.pages.dev/'
MODOS = {'simulacion': 'Simulación', 'local': 'Operación local', 'red': 'Operación por red local'}
REGISTRO = os.path.join(APP, 'registro_gemelo.log')
NOMBRE_VALIDO = re.compile(r'^[A-Za-z0-9_.\-]{1,32}$')


class Config:
    puerto = 'auto'
    direccion = None
    puerto_red = 8443
    cifrado = True


APLICACION = {'modo': None, 'red_simulado': False, 'red': None, 'url_red': None}
CAMBIO = threading.Lock()

PAGINA_LOGIN = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Gemelo digital · Ingreso</title>
<meta name="theme-color" content="#111318"><link rel="icon" href="icono.svg"><link rel="manifest" href="manifest.webmanifest">
<link rel="stylesheet" href="css/sistema.css"><style>
body{display:grid;place-items:center;padding:var(--e-4)}
.ingreso{width:min(400px,100%);display:grid;gap:var(--e-4)}
.ingreso header{display:flex;align-items:center;gap:var(--e-3)}
.ingreso header img{width:40px;height:40px}
.ingreso h1{font-size:var(--t-l);margin:0}
.error{color:var(--c-peligro);font-size:var(--t-s);min-height:1.3em;margin:0}
.ayuda{font-size:var(--t-xs);color:var(--c-texto-2);margin:0}
</style></head><body class="sd"><form method="post" action="login" class="sd-tarjeta ingreso">
<header><img src="icono.svg" alt=""><div><h1>Gemelo digital</h1><span class="secundario pequeno">Brazo XK-JS1-1 · Laboratorio de Control</span></div></header>
<label class="sd-campo">Usuario<input name="usuario" autocomplete="username" required autofocus></label>
<label class="sd-campo">Contraseña<input name="clave" type="password" autocomplete="current-password" required></label>
<p class="error" role="alert">{error}</p>
<button class="sd-boton primario">Ingresar</button>
<p class="ayuda">Observador: ve el brazo en vivo. Operador: además lo manda, siempre con alguien junto a la seta de emergencia.</p>
</form></body></html>"""


def registrar(texto):
    linea = time.strftime('%H:%M:%S ') + texto
    print(linea, flush=True)
    with open(REGISTRO, 'a', encoding='utf-8') as f:
        f.write(linea + '\n')


# ====================================================================== modos
def certificado():
    """Certificado TLS propio (autofirmado) para el acceso por red; se crea una sola vez, en Python."""
    cert, clave = os.path.join(APP, 'tls_certificado.pem'), os.path.join(APP, 'tls_clave.pem')
    if not (os.path.exists(cert) and os.path.exists(clave)):
        print('Creando el certificado del laboratorio (solo la primera vez)...', flush=True)
        certificado_tls.crear(cert, clave)
        try:
            os.chmod(clave, 0o600)
        except OSError:
            pass
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


def _activar_red():
    if APLICACION['red']:
        return
    srv = ThreadingHTTPServer(('0.0.0.0', Config.puerto_red), Manejador)
    srv.es_red = True
    srv.tls = Config.cifrado
    if srv.tls:
        srv.socket = certificado().wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    APLICACION['red'] = srv
    APLICACION['url_red'] = f"{'https' if srv.tls else 'http'}://{ip_local()}:{Config.puerto_red}/"
    registrar(f'acceso por red local: {APLICACION["url_red"]} (con usuario y contraseña)')


def _desactivar_red():
    srv = APLICACION['red']
    if not srv:
        return
    srv.shutdown()
    srv.server_close()
    APLICACION['red'] = APLICACION['url_red'] = None
    registrar('acceso por red local cerrado')


def _mando_simulacion(b):
    """En la simulación no hay brazo real: el mando de esta PC viene habilitado."""
    for _ in range(50):
        if b.conectado:
            try:
                b.habilitar_mando(True, 'local')
            except ValueError:
                pass
            return
        time.sleep(0.1)


def aplicar_modo(modo, red_simulado=False):
    """Cambia de modo: crea la conexión que corresponde (real o simulada) y abre o cierra la red."""
    global BRAZO
    if modo not in MODOS:
        raise ValueError('modo desconocido')
    if modo == 'red' and not ACCESO.hay_usuarios():
        raise ValueError('para la operación por red cree antes al menos un usuario (sección Usuarios)')
    simulado = modo == 'simulacion' or (modo == 'red' and red_simulado)
    with CAMBIO:
        if BRAZO is None or BRAZO.simulado != simulado:
            if BRAZO:
                BRAZO.cerrar()
            BRAZO = Brazo(Config.puerto, Config.direccion, simulado, REGISTRO)
        elif BRAZO.mando_de not in (None, 'local'):
            BRAZO.soltar_mando_de(BRAZO.mando_de)      # el mando remoto no sobrevive a un cambio de modo
        if modo == 'red':
            _activar_red()
        else:
            _desactivar_red()
        APLICACION['modo'], APLICACION['red_simulado'] = modo, (modo == 'red' and red_simulado)
        if modo == 'simulacion' and not BRAZO.mando:
            threading.Thread(target=_mando_simulacion, args=(BRAZO,), daemon=True).start()
    registrar(f'modo: {MODOS[modo]}' + (' (PLC simulado)' if modo == 'red' and red_simulado else ''))


def estado_aplicacion():
    b = BRAZO
    plc = None
    if b:
        plc = {'conectado': b.conectado, 'simulado': b.simulado, 'puerto': b.puerto, 'direccion': b.direccion,
               'baudios': getattr(b, 'baudios', None), 'perfil': b.perfil.nombre if b.perfil else None,
               'descripcion': getattr(b.perfil, 'descripcion', '') if b.perfil else '', 'error': b.error,
               'mando': b.mando, 'mando_de': b.mando_de}
    usuarios = acceso.cargar()
    return {'modo': APLICACION['modo'], 'nombre_modo': MODOS.get(APLICACION['modo']),
            'red_simulado': APLICACION['red_simulado'], 'url_red': APLICACION['url_red'], 'ip': ip_local(),
            'url_pagina': URL_PAGINA,
            'puerto_red': Config.puerto_red, 'plc': plc, 'puertos': serie.puertos(), 'sistema': sys.platform,
            'usuarios': [{'nombre': n, 'rol': d['rol']} for n, d in sorted(usuarios.items())],
            'conectados': sorted({u for u, _ in ACCESO.activas()})}


def administrar_usuarios(d):
    """Altas, cambios y bajas de usuarios desde el menú (solo en esta PC)."""
    accion, nombre = d.get('accion'), (d.get('nombre') or '').strip()
    if not NOMBRE_VALIDO.match(nombre):
        raise ValueError('nombre de usuario no válido: use letras, números, punto, guion o guion bajo (máx. 32)')
    u = acceso.cargar()
    if accion == 'agregar':
        if nombre in u:
            raise ValueError(f'el usuario {nombre} ya existe')
        acceso.poner_clave(u, nombre, d.get('clave') or '', d.get('rol'))
    elif accion == 'clave':
        if nombre not in u:
            raise ValueError(f'no existe el usuario {nombre}')
        acceso.poner_clave(u, nombre, d.get('clave') or '', u[nombre]['rol'])
    elif accion == 'rol':
        if nombre not in u:
            raise ValueError(f'no existe el usuario {nombre}')
        if d.get('rol') not in acceso.ROLES:
            raise ValueError('rol desconocido')
        u[nombre]['rol'] = d['rol']
    elif accion == 'quitar':
        if u.pop(nombre, None) is None:
            raise ValueError(f'no existe el usuario {nombre}')
        if BRAZO and BRAZO.mando_de == nombre:
            BRAZO.soltar_mando_de(nombre)
    else:
        raise ValueError('acción desconocida')
    acceso.guardar(u)
    registrar(f'usuarios: {accion} {nombre}' + (f' ({d.get("rol")})' if accion in ('agregar', 'rol') else ''))


# ====================================================================== servidor
class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=UI, **k)

    def log_message(self, formato, *args):
        if self.path.startswith('/api/') and self.command == 'GET':
            return                                   # las lecturas periódicas no se registran
        sys.stderr.write('%s %s\n' % (self.address_string(), formato % args))

    # -------------------------------------------------------------- sesión
    @property
    def en_esta_pc(self):
        """Conexión desde la propia PC por la puerta local (no por la de red)."""
        return self.client_address[0] in ('127.0.0.1', '::1') and not getattr(self.server, 'es_red', False)

    @property
    def local(self):
        return self.en_esta_pc and not CLAVE_LOCAL

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

    def _puede_menu(self):
        if not self.en_esta_pc:
            return False
        s = self.sesion()
        return bool(s and s['rol'] == 'operador')

    def _mismo_origen(self):
        """Protección contra páginas ajenas: las órdenes deben venir de esta misma app."""
        origen = self.headers.get('Origin')
        if origen is None:
            return self.local                         # curl en esta PC
        esquema = 'https' if getattr(self.server, 'tls', False) else 'http'
        return origen == f'{esquema}://{self.headers.get("Host")}'

    # -------------------------------------------------------------- respuestas
    def end_headers(self):
        # Otras páginas abiertas en esta PC (por ejemplo la publicada) pueden LEER el estado del brazo
        if self.local and self.command in ('GET', 'OPTIONS') and self.path.startswith(('/api/estado', '/api/info')):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
        if self.path.startswith(('/api/', '/qr.svg', '/sw.js')) or self.path in ('/', '/index.html', '/login', '/menu'):
            self.send_header('Cache-Control', 'no-store')
        elif self.path.startswith(('/js/', '/css/')):
            self.send_header('Cache-Control', 'no-cache')   # que una versión nueva de la app llegue sin limpiar el navegador
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
        datos = json.dumps({'usuario': s['usuario'], 'rol': s['rol'], 'local': self.local,
                            'menu': self.en_esta_pc and s['rol'] == 'operador',
                            'modo': MODOS.get(APLICACION['modo'])})
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
            if s and BRAZO:
                BRAZO.soltar_mando_de(s['usuario'])
            return self._ir('login', [self._cookie('', 0)])
        s = self.sesion()
        # menú de inicio: solo en esta PC
        if ruta == '/menu':
            if not self._puede_menu():
                return self._ir('./' if s else 'login')
            with open(os.path.join(APP, 'menu.html'), encoding='utf-8') as f:
                return self._html(200, f.read())
        if ruta == '/qr.svg':
            if not self._puede_menu():
                return self._json(403, {'ok': False, 'error': 'solo desde la PC del laboratorio'})
            cual = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('d', ['pagina'])[0]
            texto = APLICACION['url_red'] if cual == 'red' else URL_PAGINA
            if not texto:
                return self._json(404, {'ok': False, 'error': 'el acceso por red no está activo'})
            cuerpo = qr.svg(texto).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'image/svg+xml')
            self.send_header('Content-Length', str(len(cuerpo)))
            self.end_headers()
            return self.wfile.write(cuerpo)
        if ruta == '/api/app':
            if not self._puede_menu():
                return self._json(403, {'ok': False, 'error': 'solo desde la PC del laboratorio'})
            return self._json(200, estado_aplicacion())
        if ruta.startswith('/api/'):
            if not s:
                return self._json(401, {'ok': False, 'error': 'sesión vencida: vuelva a ingresar'})
            if BRAZO is None:
                return self._json(503, {'ok': False, 'error': 'elija un modo en el menú de la app'})
            if ruta == '/api/info':
                return self._json(200, BRAZO.info())
            if ruta == '/api/estado':
                return self._json(200, BRAZO.leer_estado())
            if ruta == '/api/sesion':
                return self._json(200, {'usuario': s['usuario'], 'rol': s['rol'], 'local': self.local,
                                        'conectados': ACCESO.activas()})
            return self._json(404, {'ok': False, 'error': 'ruta desconocida'})
        if ruta in ('/', '/index.html'):
            if not s:
                return self._ir('login')
            if BRAZO is None and self._puede_menu():
                return self._ir('menu')
            return self._index(s)
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
                registrar(f'ingreso fallido de "{usuario}" desde {self.client_address[0]}')
                return self._html(401, PAGINA_LOGIN.replace('{error}', html.escape(str(ex))))
            registrar(f'ingreso de {usuario} ({rol}) desde {self.client_address[0]}')
            return self._ir('./', [self._cookie(token, acceso.DURACION)])
        s = self.sesion()
        if not s:
            return self._json(401, {'ok': False, 'error': 'sesión vencida: vuelva a ingresar'})
        if not self._mismo_origen():
            return self._json(403, {'ok': False, 'error': 'solo lectura: las órdenes se dan desde la app del gemelo'})
        # menú: cambio de modo y usuarios (solo en esta PC)
        if ruta.startswith('/api/app/'):
            if not self._puede_menu():
                return self._json(403, {'ok': False, 'error': 'solo desde la PC del laboratorio'})
            try:
                datos = json.loads(cuerpo or b'{}')
                if ruta == '/api/app/modo':
                    aplicar_modo(datos.get('modo'), bool(datos.get('red_simulado')))
                elif ruta == '/api/app/usuarios':
                    administrar_usuarios(datos)
                else:
                    return self._json(404, {'ok': False, 'error': 'ruta desconocida'})
                return self._json(200, dict(estado_aplicacion(), ok=True))
            except ValueError as ex:
                return self._json(400, {'ok': False, 'error': str(ex)})
            except OSError as ex:                     # p. ej. el puerto de red ya está en uso
                return self._json(500, {'ok': False, 'error': f'no se pudo abrir el acceso por red: {ex}'})
        if BRAZO is None:
            return self._json(503, {'ok': False, 'error': 'elija un modo en el menú de la app'})
        if s['rol'] != 'operador' and (ruta in SOLO_OPERADOR or ruta.startswith('/api/orden/')):
            registrar(f'RECHAZADO {ruta} de {s["usuario"]} ({s["rol"]}): solo puede ver')
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
            registrar(f'RECHAZADO {ruta} de {s["usuario"]}: {ex}')
            self._json(400, {'ok': False, 'error': str(ex)})
        except Exception as ex:                       # error de comunicación u otro
            self._json(500, {'ok': False, 'error': str(ex)})


def vigilar_mando():
    """Si quien tiene el mando ya no tiene sesión (salió o venció), el mando se suelta."""
    while True:
        time.sleep(15)
        b = BRAZO
        if not b:
            continue
        quien = b.mando_de
        if b.mando and quien not in (None, 'local') and quien not in {u for u, _ in ACCESO.activas()}:
            b.soltar_mando_de(quien)


def main():
    global CLAVE_LOCAL
    ap = argparse.ArgumentParser(description='Gemelo digital del brazo XK-JS1-1 (PLC S7-200 por PPI)')
    ap.add_argument('--modo', choices=['menu', 'simulacion', 'local', 'red'], default='menu',
                    help='modo al abrir (por defecto el menú)')
    ap.add_argument('--red-simulado', action='store_true', help='con --modo red: usar el PLC simulado')
    ap.add_argument('--simulado', action='store_true', help='(compatibilidad) igual que --modo simulacion')
    ap.add_argument('--red', action='store_true', help='(compatibilidad) igual que --modo red')
    ap.add_argument('--puerto', default='auto', help='puerto serie del cable, p. ej. COM3 o /dev/ttyUSB0 '
                    '(por defecto lo busca entre los presentes)')
    ap.add_argument('--direccion', type=int, default=None, help='dirección PPI del PLC (por defecto la busca)')
    ap.add_argument('--http', type=int, default=8050, help='puerto local de la ventana (por defecto 8050)')
    ap.add_argument('--puerto-red', type=int, default=8443, help='puerto del acceso por red (por defecto 8443)')
    ap.add_argument('--sin-cifrado', action='store_true', help='red local por http (las contraseñas viajan en claro)')
    ap.add_argument('--clave-local', action='store_true', help='pedir contraseña también en esta PC')
    ap.add_argument('--navegador', action='store_true', help='abrir en el navegador en vez de la ventana')
    ap.add_argument('--sin-ventana', action='store_true', help='solo el servidor (sin ventana ni navegador)')
    a = ap.parse_args()
    CLAVE_LOCAL = a.clave_local
    Config.puerto, Config.direccion, Config.puerto_red, Config.cifrado = \
        a.puerto, a.direccion, a.puerto_red, not a.sin_cifrado
    modo = a.modo
    if a.red:
        modo, a.red_simulado = 'red', a.red_simulado or a.simulado
    elif a.simulado:
        modo = 'simulacion'
    if a.clave_local and not ACCESO.hay_usuarios():
        raise SystemExit('Con --clave-local hace falta al menos un usuario operador (usuarios.py agregar ...).')

    principal = ThreadingHTTPServer(('127.0.0.1', a.http), Manejador)
    inicio = 'menu'
    if modo != 'menu':
        try:
            aplicar_modo(modo, a.red_simulado)
            inicio = ''
        except ValueError as ex:
            print(f'No se pudo abrir el modo «{MODOS[modo]}»: {ex}. Se abre el menú.', flush=True)
    url = f'http://localhost:{a.http}/{inicio}'
    print(f'Gemelo digital en http://localhost:{a.http}/  (cierre la ventana o Ctrl+C para salir)', flush=True)
    threading.Thread(target=vigilar_mando, daemon=True).start()

    try:
        if not a.navegador and not a.sin_ventana and ventana.disponible():
            threading.Thread(target=principal.serve_forever, daemon=True).start()
            ventana.abrir(url)
        else:
            if not a.sin_ventana:
                threading.Timer(1.0, lambda: webbrowser.open(url)).start()
            principal.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if BRAZO:
            BRAZO.cerrar()                     # para el brazo si se movía por orden de la PC
        _desactivar_red()
        principal.server_close()
        print('\nApp cerrada.')


if __name__ == '__main__':
    main()
