"""Puerto serie mínimo para el cable USB-PPI (8 bits, paridad par, 1 bit de parada), sin dependencias.

- Windows: API Win32 (CreateFile, SetCommState, ReadFile...) a través de ctypes.
- Linux/macOS: termios.

Solo lo que necesita el protocolo PPI: abrir a 9600 o 19200 baudios, escribir, leer lo que
llegue con una espera corta y vaciar la entrada.
"""
import os
import sys
import time

ES_WINDOWS = sys.platform == 'win32'


def puertos():
    """Puertos serie presentes, los USB primero. Devuelve [(nombre, descripción), ...]."""
    if ES_WINDOWS:
        import winreg
        lista = []
        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DEVICEMAP\SERIALCOMM')
        except OSError:
            return []
        i = 0
        while True:
            try:
                dispositivo, com, _ = winreg.EnumValue(k, i)
            except OSError:
                break
            lista.append((str(com), str(dispositivo)))
            i += 1
        usb = lambda d: any(t in d.upper() for t in ('USB', 'CH34', 'VCP', 'SILAB', 'PROLIFIC', 'FTDI'))
        numero = lambda c: int(''.join(ch for ch in c if ch.isdigit()) or 0)
        return sorted(lista, key=lambda x: (not usb(x[1]), numero(x[0])))
    import glob
    return [(p, 'USB') for p in sorted(glob.glob('/dev/ttyUSB*')) + sorted(glob.glob('/dev/ttyACM*'))]


if ES_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    _INVALIDO = ctypes.c_void_p(-1).value
    _MAXDWORD = 0xFFFFFFFF

    class _DCB(ctypes.Structure):
        _fields_ = [('DCBlength', wintypes.DWORD), ('BaudRate', wintypes.DWORD), ('flags', wintypes.DWORD),
                    ('wReserved', wintypes.WORD), ('XonLim', wintypes.WORD), ('XoffLim', wintypes.WORD),
                    ('ByteSize', ctypes.c_ubyte), ('Parity', ctypes.c_ubyte), ('StopBits', ctypes.c_ubyte),
                    ('XonChar', ctypes.c_char), ('XoffChar', ctypes.c_char), ('ErrorChar', ctypes.c_char),
                    ('EofChar', ctypes.c_char), ('EvtChar', ctypes.c_char), ('wReserved1', wintypes.WORD)]

    class _TIEMPOS(ctypes.Structure):
        _fields_ = [(n, wintypes.DWORD) for n in ('ReadIntervalTimeout', 'ReadTotalTimeoutMultiplier',
                                                  'ReadTotalTimeoutConstant', 'WriteTotalTimeoutMultiplier',
                                                  'WriteTotalTimeoutConstant')]

    _k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _k32.CreateFileW.restype = wintypes.HANDLE
    _k32.GetCommState.argtypes = [wintypes.HANDLE, ctypes.POINTER(_DCB)]
    _k32.SetCommState.argtypes = [wintypes.HANDLE, ctypes.POINTER(_DCB)]
    _k32.SetCommTimeouts.argtypes = [wintypes.HANDLE, ctypes.POINTER(_TIEMPOS)]
    _k32.SetupComm.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
    _k32.PurgeComm.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                              ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _k32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                               ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    for _f in ('GetCommState', 'SetCommState', 'SetCommTimeouts', 'SetupComm', 'PurgeComm',
               'ReadFile', 'WriteFile', 'CloseHandle'):
        getattr(_k32, _f).restype = wintypes.BOOL

    def _error(que):
        n = ctypes.get_last_error()
        return OSError(n, f'{que}: {ctypes.FormatError(n).strip()}')

    class Puerto:
        ESPERA_MS = 20          # cuánto espera leer() al primer byte si no hay nada

        def __init__(self, nombre, baudios):
            self.nombre, self.baudios, self.h = nombre, baudios, None

        def abrir(self):
            ruta = self.nombre if self.nombre.startswith('\\\\') else '\\\\.\\' + self.nombre
            h = _k32.CreateFileW(ruta, 0x80000000 | 0x40000000, 0, None, 3, 0, None)   # lectura+escritura
            if h in (None, _INVALIDO):
                raise _error(f'no se pudo abrir {self.nombre}')
            try:
                _k32.SetupComm(h, 4096, 4096)
                dcb = _DCB()
                dcb.DCBlength = ctypes.sizeof(_DCB)
                if not _k32.GetCommState(h, ctypes.byref(dcb)):
                    raise _error('GetCommState')
                dcb.BaudRate = self.baudios
                dcb.ByteSize, dcb.Parity, dcb.StopBits = 8, 2, 0        # 8 bits, paridad par, 1 parada
                # fBinary, fParity, DTR y RTS activos (como Linux al abrir), sin control de flujo
                dcb.flags = 0x0001 | 0x0002 | (1 << 4) | (1 << 12)
                if not _k32.SetCommState(h, ctypes.byref(dcb)):
                    raise _error('SetCommState (¿velocidad no admitida?)')
                t = _TIEMPOS(_MAXDWORD, _MAXDWORD, self.ESPERA_MS, 0, 2000)
                if not _k32.SetCommTimeouts(h, ctypes.byref(t)):
                    raise _error('SetCommTimeouts')
                _k32.PurgeComm(h, 0x0F)
            except Exception:
                _k32.CloseHandle(h)
                raise
            self.h = h

        def cerrar(self):
            if self.h is not None:
                _k32.CloseHandle(self.h)
                self.h = None

        def vaciar_entrada(self):
            _k32.PurgeComm(self.h, 0x0A)            # PURGE_RXABORT | PURGE_RXCLEAR

        def escribir(self, datos):
            n = wintypes.DWORD(0)
            buf = ctypes.create_string_buffer(bytes(datos), len(datos))
            if not _k32.WriteFile(self.h, buf, len(datos), ctypes.byref(n), None):
                raise _error(f'escritura en {self.nombre}')

        def leer(self):
            """Lo que haya llegado; si no hay nada, espera hasta ESPERA_MS al primer byte."""
            buf = ctypes.create_string_buffer(512)
            n = wintypes.DWORD(0)
            if not _k32.ReadFile(self.h, buf, 512, ctypes.byref(n), None):
                raise _error(f'lectura de {self.nombre}')
            return buf.raw[:n.value]

else:
    import select
    import termios

    _BAUDIOS = {9600: termios.B9600, 19200: termios.B19200}

    class Puerto:
        ESPERA_S = 0.02

        def __init__(self, nombre, baudios):
            self.nombre, self.baudios, self.fd = nombre, baudios, None

        def abrir(self):
            fd = os.open(self.nombre, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            try:
                a = termios.tcgetattr(fd)
                a[0] = a[1] = a[3] = 0
                a[2] = termios.CS8 | termios.PARENB | termios.CREAD | termios.CLOCAL
                a[4] = a[5] = _BAUDIOS[self.baudios]
                termios.tcsetattr(fd, termios.TCSANOW, a)
                termios.tcflush(fd, termios.TCIOFLUSH)
            except Exception:
                os.close(fd)
                raise
            self.fd = fd

        def cerrar(self):
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None

        def vaciar_entrada(self):
            termios.tcflush(self.fd, termios.TCIFLUSH)

        def escribir(self, datos):
            os.write(self.fd, bytes(datos))

        def leer(self):
            r, _, _ = select.select([self.fd], [], [], self.ESPERA_S)
            if not r:
                return b''
            try:
                return os.read(self.fd, 512)
            except BlockingIOError:
                return b''


def espera(segundos):
    """time.sleep que no se pasa de largo con tiempos muy cortos (Windows redondea a ~15 ms)."""
    fin = time.perf_counter() + segundos
    while True:
        falta = fin - time.perf_counter()
        if falta <= 0:
            return
        time.sleep(falta if falta > 0.002 else 0)
