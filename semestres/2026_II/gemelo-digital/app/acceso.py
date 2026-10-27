"""Usuarios, contraseñas y sesiones de la app del gemelo (red local).

- Roles: "observador" (solo ve el brazo) y "operador" (lo manda y puede dar paro).
- Las contraseñas se guardan con PBKDF2-SHA256 y sal aleatoria en usuarios.json; nunca en claro.
- Sesión por cookie (HttpOnly, SameSite=Strict) que vence a las 8 h sin uso.
- Tras 5 intentos fallidos desde una misma dirección, esa dirección espera 60 s.
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time

APP = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(APP, 'usuarios.json')
ROLES = ('observador', 'operador')
ITERACIONES = 200_000
DURACION = 8 * 3600
MAX_FALLOS, ESPERA = 5, 60


def _hash(clave, sal):
    return hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal, ITERACIONES).hex()


def cargar(archivo=ARCHIVO):
    try:
        with open(archivo, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def guardar(usuarios, archivo=ARCHIVO):
    tmp = archivo + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(usuarios, f, indent=2, ensure_ascii=False)
    os.chmod(tmp, 0o600)
    os.replace(tmp, archivo)


def poner_clave(usuarios, nombre, clave, rol):
    if rol not in ROLES:
        raise ValueError(f'rol desconocido: {rol} (use {" u ".join(ROLES)})')
    if len(clave) < 8:
        raise ValueError('la contraseña debe tener al menos 8 caracteres')
    sal = secrets.token_bytes(16)
    usuarios[nombre] = {'rol': rol, 'sal': sal.hex(), 'hash': _hash(clave, sal)}


class Acceso:
    def __init__(self, archivo=ARCHIVO):
        self.archivo = archivo
        self.sesiones = {}            # token -> {usuario, rol, vence, ip}
        self.fallos = {}              # ip -> (cantidad, bloqueado_hasta)
        self.lock = threading.Lock()

    def hay_usuarios(self):
        return bool(cargar(self.archivo))

    def entrar(self, usuario, clave, ip):
        """Devuelve (token, rol) o levanta ValueError con un mensaje para mostrar."""
        with self.lock:
            n, hasta = self.fallos.get(ip, (0, 0))
            if time.time() < hasta:
                raise ValueError(f'demasiados intentos: espere {int(hasta - time.time()) + 1} s')
        u = cargar(self.archivo).get(usuario)
        ok = bool(u) and hmac.compare_digest(_hash(clave, bytes.fromhex(u['sal'])), u['hash'])
        if not u:
            _hash(clave, b'x' * 16)   # mismo tiempo de respuesta exista o no el usuario
        with self.lock:
            if not ok:
                n += 1
                self.fallos[ip] = (0, time.time() + ESPERA) if n >= MAX_FALLOS else (n, 0)
                raise ValueError('usuario o contraseña incorrectos')
            self.fallos.pop(ip, None)
            token = secrets.token_urlsafe(32)
            self.sesiones[token] = {'usuario': usuario, 'rol': u['rol'], 'vence': time.time() + DURACION, 'ip': ip}
            return token, u['rol']

    def sesion(self, token):
        if not token:
            return None
        with self.lock:
            s = self.sesiones.get(token)
            if not s:
                return None
            if time.time() > s['vence']:
                del self.sesiones[token]
                return None
            # El rol se vuelve a leer: si se cambia o se borra el usuario, vale en la siguiente petición
            u = cargar(self.archivo).get(s['usuario'])
            if not u:
                del self.sesiones[token]
                return None
            s['rol'] = u['rol']
            s['vence'] = time.time() + DURACION
            return dict(s)

    def salir(self, token):
        with self.lock:
            return self.sesiones.pop(token, None)

    def activas(self):
        with self.lock:
            ahora = time.time()
            return sorted({(s['usuario'], s['rol']) for s in self.sesiones.values() if s['vence'] > ahora})
