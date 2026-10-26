"""Ventana de escritorio de la app (GTK 3 + WebKitGTK, incluidos en Linux Mint/Ubuntu).

Muestra la interfaz servida por la app en una ventana propia, sin pestañas ni barra de
direcciones. Si las bibliotecas no están, la app abre el navegador en su lugar.
"""


def disponible():
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
