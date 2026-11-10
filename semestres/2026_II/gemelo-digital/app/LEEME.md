# App del gemelo digital del brazo XK-JS1-1

Una sola app, para **Linux y Windows**, con un menú de inicio de tres modos:

| Modo | Para qué |
|---|---|
| **Simulación** | practicar sin brazo ni cable (PLC simulado dentro de la app) |
| **Operación local** | ver y mandar el brazo real desde esta PC (cable USB-PPI al puerto 0 del PLC) |
| **Operación por red local** | lo mismo, y además celulares y otras PC de la red entran con usuario y contraseña (`https://IP:8443/`) |

Desde el menú también se crean los usuarios del acceso por red. El botón **Menú** de la barra del gemelo
vuelve al menú para cambiar de modo sin cerrar la app.

## Abrir

- **Linux**: menú de aplicaciones → *Gemelo digital del brazo* (se crea una vez con `./instalar_acceso.sh`),
  o `./iniciar_gemelo.sh` en una terminal. Si la VM de Windows XP está abierta, el USB del cable debe estar
  **desmarcado** en su menú Dispositivos → USB.
- **Windows**: instale Python 3 (python.org, marcando *Add python.exe to PATH*) y haga doble clic en
  `Gemelo digital.bat`. `Crear acceso directo.bat` lo pone en el escritorio.

Para comprobar el cable sin mover nada: `python3 probar_plc.py` (Windows: `Probar conexion PLC.bat`).

## Documentos (carpeta `documentos`)

- `manual_linux.pdf` y `manual_windows.pdf`: instalación y uso en cada sistema.
- `guia_completa_brazo.pdf`: la planta, los programas del PLC en ladder, el modelado y el software.
- `arquitectura_gemelo_digital.pdf`: páginas web, protocolo PPI y modos de mando en detalle.

## Contenido

| Archivo | Para qué |
|---|---|
| `gemelo_brazo.py` | Programa principal: menú de modos, servidor local y de red, API |
| `brazo.py`, `ppi.py`, `serie.py` | Comunicación con el PLC (PPI sobre el puerto serie de Linux o Windows), perfiles, estimador y PLC simulado |
| `acceso.py`, `usuarios.py`, `certificado_tls.py` | Usuarios, sesiones y certificado HTTPS del acceso por red |
| `ventana.py` | Ventana propia: GTK + WebKit en Linux, Edge en modo aplicación en Windows |
| `menu.html`, `ui/` | Interfaz: menú y página del gemelo |
| `probar_plc.py` | Diagnóstico de solo lectura |
| `*.sh` / `*.bat` | Lanzadores de Linux / Windows |
| `empaquetar.py` | (Repositorio) actualiza `ui/` y exporta la app autónoma |

Datos propios de cada PC (no se comparten ni se suben al repositorio): `usuarios.json`,
`tls_certificado.pem`, `tls_clave.pem`, `calibracion.json`, `registro_gemelo.log`.
