"""Cliente PPI para el S7-200 por el cable USB-PPI (sin dependencias, solo Linux/macOS).

Implementa las peticiones S7 "Read Var" (0x04) y "Write Var" (0x05) sobre el protocolo
PPI (FDL, 8 bits, paridad par, 1 bit de parada), como lo hace libnodave. La PC es el
maestro (dirección 0) y el PLC el esclavo.

Las escrituras solo se aceptan dentro de las zonas que pasa quien crea el cliente
(`zonas_escritura`): cualquier otra dirección levanta un error sin tocar el puerto.
"""
import os
import select
import termios
import threading
import time

AREAS = {'I': 0x81, 'Q': 0x82, 'M': 0x83, 'V': 0x84, 'SM': 0x05}
BAUDIOS = {9600: termios.B9600, 19200: termios.B19200}


class ErrorPPI(IOError):
    pass


class ClientePPI:
    def __init__(self, puerto='/dev/ttyUSB0', plc=6, pc=0, baudios=19200, zonas_escritura=()):
        self.puerto, self.plc, self.pc, self.baudios = puerto, plc, pc, baudios
        self.zonas = list(zonas_escritura)          # [(area, byte_inicio, byte_fin_inclusive)]
        self.fd = None
        self.lock = threading.Lock()
        self._fcb = False
        self._ref = 0

    # ------------------------------------------------------------------ puerto
    def abrir(self):
        fd = os.open(self.puerto, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        a = termios.tcgetattr(fd)
        a[0] = a[1] = a[3] = 0
        a[2] = termios.CS8 | termios.PARENB | termios.CREAD | termios.CLOCAL
        a[4] = a[5] = BAUDIOS[self.baudios]
        termios.tcsetattr(fd, termios.TCSANOW, a)
        termios.tcflush(fd, termios.TCIOFLUSH)
        self.fd = fd

    def cerrar(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _leer(self, espera):
        datos = b''
        fin = time.time() + espera
        while time.time() < fin:
            r, _, _ = select.select([self.fd], [], [], 0.02)
            if not r:
                continue
            try:
                d = os.read(self.fd, 512)
            except BlockingIOError:
                d = b''
            datos += d
            if datos[:1] == b'\xe5':
                break
            if datos[:1] == b'\x68' and len(datos) >= 4 and len(datos) >= datos[1] + 6:
                break
        return datos

    def _sd2(self, fc, pdu):
        cuerpo = bytes([self.plc, self.pc, fc]) + pdu
        return bytes([0x68, len(cuerpo), len(cuerpo), 0x68]) + cuerpo + bytes([sum(cuerpo) & 0xFF, 0x16])

    def _sd1(self, fc):
        cuerpo = bytes([self.plc, self.pc, fc])
        return bytes([0x10]) + cuerpo + bytes([sum(cuerpo) & 0xFF, 0x16])

    def _intercambio(self, pdu):
        """Envía un PDU S7 y devuelve el PDU de la respuesta."""
        if self.fd is None:
            self.abrir()
        termios.tcflush(self.fd, termios.TCIFLUSH)
        os.write(self.fd, self._sd2(0x7C if self._fcb else 0x6C, pdu))
        self._fcb = not self._fcb
        r = self._leer(0.4)
        if not r.startswith(b'\xe5'):
            raise ErrorPPI('el PLC no acusó la petición' + (f' ({r.hex(" ")})' if r else ''))
        for intento in range(8):
            os.write(self.fd, self._sd1(0x5C if intento % 2 == 0 else 0x7C))
            r = self._leer(0.4)
            if r.startswith(b'\x68') and len(r) >= 9:
                le = r[1]
                cuerpo = r[4:4 + le]
                if len(r) < le + 6 or (sum(cuerpo) & 0xFF) != r[4 + le]:
                    raise ErrorPPI('respuesta con suma de control incorrecta')
                return cuerpo[3:]
            time.sleep(0.01)
        raise ErrorPPI('el PLC no entregó la respuesta')

    def _cabecera(self, param, datos=b''):
        self._ref = (self._ref + 1) & 0xFFFF
        return bytes([0x32, 0x01, 0, 0, self._ref >> 8, self._ref & 0xFF,
                      len(param) >> 8, len(param) & 0xFF, len(datos) >> 8, len(datos) & 0xFF]) + param + datos

    @staticmethod
    def _item(area, ts, n, direccion_bits):
        db = 1 if area == 'V' else 0
        return bytes([0x12, 0x0A, 0x10, ts, n >> 8, n & 0xFF, db >> 8, db & 0xFF, AREAS[area]]) + \
            direccion_bits.to_bytes(3, 'big')

    @staticmethod
    def _revisar(pdu, funcion):
        if len(pdu) < 14 or pdu[0] != 0x32 or pdu[1] != 0x03:
            raise ErrorPPI('respuesta S7 inesperada: ' + pdu.hex(' '))
        if pdu[10] or pdu[11]:
            raise ErrorPPI(f'el PLC devolvió error S7 {pdu[10]:02X}{pdu[11]:02X}')
        if pdu[12] != funcion:
            raise ErrorPPI('respuesta a otra función')
        return pdu[14:]

    # ------------------------------------------------------------------ API
    def leer(self, area, byte, n):
        """Lee n bytes desde area/byte. Devuelve bytes."""
        with self.lock:
            pdu = self._intercambio(self._cabecera(bytes([0x04, 0x01]) + self._item(area, 0x02, n, byte * 8)))
            datos = self._revisar(pdu, 0x04)
            if datos[0] != 0xFF:
                raise ErrorPPI(f'lectura de {area}B{byte} rechazada (0x{datos[0]:02X})')
            return datos[4:4 + n]

    def _permitido(self, area, desde, hasta):
        return any(a == area and z0 <= desde and hasta <= z1 for a, z0, z1 in self.zonas)

    def escribir(self, area, byte, datos):
        """Escribe bytes en area/byte (solo dentro de las zonas permitidas)."""
        datos = bytes(datos)
        if not self._permitido(area, byte, byte + len(datos) - 1):
            raise ErrorPPI(f'escritura en {area}B{byte} fuera de las zonas permitidas')
        with self.lock:
            param = bytes([0x05, 0x01]) + self._item(area, 0x02, len(datos), byte * 8)
            carga = bytes([0x00, 0x04, (len(datos) * 8) >> 8, (len(datos) * 8) & 0xFF]) + datos
            pdu = self._intercambio(self._cabecera(param, carga))
            r = self._revisar(pdu, 0x05)
            if r[:1] != b'\xff':
                raise ErrorPPI(f'escritura en {area}B{byte} rechazada')

    def escribir_bit(self, area, byte, bit, valor):
        """Escribe un solo bit (por ejemplo V104.1) sin tocar los demás del byte."""
        if not self._permitido(area, byte, byte):
            raise ErrorPPI(f'escritura en {area}{byte}.{bit} fuera de las zonas permitidas')
        with self.lock:
            param = bytes([0x05, 0x01]) + self._item(area, 0x01, 1, byte * 8 + bit)
            carga = bytes([0x00, 0x03, 0x00, 0x01, 1 if valor else 0])
            pdu = self._intercambio(self._cabecera(param, carga))
            r = self._revisar(pdu, 0x05)
            if r[:1] != b'\xff':
                raise ErrorPPI(f'escritura en {area}{byte}.{bit} rechazada')


def buscar_plc(puerto, direcciones=range(1, 32), baudios=(19200, 9600)):
    """Prueba direcciones y velocidades con una lectura de IB0. Devuelve (direccion, baudios) o None."""
    for b in baudios:
        for d in direcciones:
            c = ClientePPI(puerto, plc=d, baudios=b)
            try:
                c.abrir()
                c.leer('I', 0, 1)
                return d, b
            except (ErrorPPI, OSError):
                pass
            finally:
                c.cerrar()
    return None
