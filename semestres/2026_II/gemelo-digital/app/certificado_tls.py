"""Certificado TLS autofirmado (RSA 2048, SHA-256) generado solo con la biblioteca estándar.

Windows no trae el programa openssl; este módulo crea los mismos dos archivos PEM que la app
de Linux (certificado y clave privada) para el acceso por red con HTTPS.
"""
import base64
import datetime
import hashlib
import secrets

_PRIMOS_CHICOS = [p for p in range(3, 2000, 2) if all(p % d for d in range(3, int(p ** 0.5) + 1, 2))]


def _es_primo(n, rondas=40):
    for p in _PRIMOS_CHICOS:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rondas):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _primo(bits):
    while True:
        n = secrets.randbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if _es_primo(n):
            return n


def _clave_rsa(bits=2048, e=65537):
    while True:
        p, q = _primo(bits // 2), _primo(bits // 2)
        if p == q:
            continue
        fi = (p - 1) * (q - 1)
        try:
            d = pow(e, -1, fi)
        except ValueError:          # e no es coprimo con fi
            continue
        n = p * q
        if n.bit_length() == bits:
            return n, e, d, p, q


# ------------------------------------------------------------------ DER mínimo
def _largo(n):
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, 'big')
    return bytes([0x80 | len(b)]) + b


def _tlv(etiqueta, contenido):
    return bytes([etiqueta]) + _largo(len(contenido)) + contenido


def _entero(n):
    return _tlv(0x02, n.to_bytes(n.bit_length() // 8 + 1, 'big'))


def _sec(*partes):
    return _tlv(0x30, b''.join(partes))


_SHA256_RSA = _sec(bytes.fromhex('06092a864886f70d01010b'), b'\x05\x00')
_RSA = _sec(bytes.fromhex('06092a864886f70d010101'), b'\x05\x00')
_SHA256 = _sec(bytes.fromhex('0609608648016503040201'), b'\x05\x00')


def _nombre(cn):
    atributo = _sec(bytes.fromhex('0603550403'), _tlv(0x0C, cn.encode('utf-8')))
    return _sec(_tlv(0x31, atributo))


def _hora(t):
    return _tlv(0x17, t.strftime('%y%m%d%H%M%SZ').encode())


def _pem(etiqueta, der):
    b = base64.b64encode(der).decode()
    lineas = '\n'.join(b[i:i + 64] for i in range(0, len(b), 64))
    return f'-----BEGIN {etiqueta}-----\n{lineas}\n-----END {etiqueta}-----\n'


def crear(archivo_cert, archivo_clave, cn='gemelo-brazo-xk-js1-1', dias=3650):
    n, e, d, p, q = _clave_rsa()
    ahora = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    validez = _sec(_hora(ahora - datetime.timedelta(days=1)), _hora(ahora + datetime.timedelta(days=dias)))
    clave_publica = _sec(_RSA, _tlv(0x03, b'\x00' + _sec(_entero(n), _entero(e))))
    # extensiones: no es una autoridad certificadora; nombres: el del certificado y localhost
    san = _sec(_tlv(0x82, cn.encode()), _tlv(0x82, b'localhost'), _tlv(0x87, bytes([127, 0, 0, 1])))
    extensiones = _tlv(0xA3, _sec(
        _sec(bytes.fromhex('0603551d13'), _tlv(0x04, _sec())),
        _sec(bytes.fromhex('0603551d11'), _tlv(0x04, san))))
    tbs = _sec(_tlv(0xA0, _entero(2)), _entero(secrets.randbits(63) | 1), _SHA256_RSA,
               _nombre(cn), validez, _nombre(cn), clave_publica, extensiones)
    # firma PKCS#1 v1.5 con SHA-256
    info = _sec(_SHA256, _tlv(0x04, hashlib.sha256(tbs).digest()))
    k = (n.bit_length() + 7) // 8
    em = b'\x00\x01' + b'\xff' * (k - len(info) - 3) + b'\x00' + info
    firma = pow(int.from_bytes(em, 'big'), d, n).to_bytes(k, 'big')
    cert = _sec(tbs, _SHA256_RSA, _tlv(0x03, b'\x00' + firma))
    clave = _sec(_entero(0), _entero(n), _entero(e), _entero(d), _entero(p), _entero(q),
                 _entero(d % (p - 1)), _entero(d % (q - 1)), _entero(pow(q, -1, p)))
    with open(archivo_clave, 'w', encoding='ascii') as f:
        f.write(_pem('RSA PRIVATE KEY', clave))
    with open(archivo_cert, 'w', encoding='ascii') as f:
        f.write(_pem('CERTIFICATE', cert))
