"""Ventana de escritorio de la app.

- Windows: Microsoft Edge (o Google Chrome) en modo aplicación: una ventana propia, sin pestañas
  ni barra de direcciones, con un perfil aparte. Al cerrarla se cierra la app.
- Linux: GTK 3 + WebKitGTK (incluidos en Linux Mint/Ubuntu).

Si no hay ninguna de las dos, la app abre el navegador predeterminado en su lugar.
"""
import os
import shutil
import subprocess
import sys
import time

APP = os.path.dirname(os.path.abspath(__file__))


def _navegador_windows():
    rutas = []
    for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), os.environ.get('LOCALAPPDATA')):
        if base:
            rutas += [os.path.join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
                      os.path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe')]
    rutas += [shutil.which('msedge') or '', shutil.which('chrome') or '']
    return next((r for r in rutas if r and os.path.isfile(r)), None)


def disponible():
    if sys.platform == 'win32':
        return _navegador_windows() is not None
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        gi.require_version('WebKit2', '4.1')
        from gi.repository import Gtk, WebKit2  # noqa: F401
        return True
    except (ImportError, ValueError):
        return False


def abrir(url, al_cerrar=None):
    """Abre la ventana y bloquea hasta que se cierra."""
    if sys.platform == 'win32':
        perfil = os.path.join(APP, 'perfil_ventana')       # perfil propio: el proceso termina al cerrar
        p = subprocess.Popen([_navegador_windows(), f'--app={url}', f'--user-data-dir={perfil}',
                              '--no-first-run', '--no-default-browser-check', '--window-size=1440,900'])
        try:
            while p.poll() is None:                         # así Ctrl+C en la consola sigue funcionando
                time.sleep(0.3)
        finally:
            if al_cerrar:
                al_cerrar()
        return

    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('WebKit2', '4.1')
    from gi.repository import Gtk, WebKit2

    vista = WebKit2.WebView()
    ajustes = vista.get_settings()
    ajustes.set_enable_webgl(True)
    ajustes.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.ALWAYS)
    ajustes.set_enable_developer_extras(True)          # clic derecho > Inspeccionar, para diagnosticar
    ajustes.set_enable_write_console_messages_to_stdout(True)
    # Los diálogos confirm() de la página (habilitar mando, borrar secuencia) funcionan por defecto

    ventana = Gtk.Window(title='Gemelo digital · Brazo XK-JS1-1')
    ventana.set_default_size(1440, 900)
    ventana.add(vista)

    def cerrar(*_):
        if al_cerrar:
            al_cerrar()
        Gtk.main_quit()

    ventana.connect('destroy', cerrar)
    vista.load_uri(url)
    ventana.show_all()
    Gtk.main()
