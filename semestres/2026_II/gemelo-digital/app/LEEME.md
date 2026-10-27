# App del gemelo digital del brazo XK-JS1-1

Ventana con el visor 3D del brazo, conectada al PLC S7-200 por el cable USB-PPI.
Funciona sin internet y sin instalar nada (Python 3 y WebKitGTK ya vienen en Linux Mint/Ubuntu).

## Abrir

- Desde el menú de aplicaciones: **Gemelo digital del brazo** (o "(simulado)" para practicar sin PLC).
  Los accesos se crean una vez con `./instalar_acceso.sh`.
- Desde una terminal en esta carpeta: `./iniciar_gemelo.sh` (opciones: `--simulado`, `--direccion 6`,
  `--puerto /dev/ttyUSB0`, `--navegador`).

Antes de abrirla: cable USB-PPI enchufado al puerto 0 del PLC y, si la VM de Windows XP está abierta,
el USB **desmarcado** en su menú Dispositivos → USB.

## Desde celulares de la red local

`python3 usuarios.py agregar NOMBRE --rol operador` (u `observador`) y luego el acceso
**Gemelo digital del brazo (red local)**: la terminal muestra la dirección `https://IP:8443/` para los
celulares. Observador: solo ve. Operador: manda (uno a la vez; los demás pueden dar paro).

## Uso

- La barra superior dice si hay PLC, qué programa tiene y si el mando está habilitado.
- El modelo 3D sigue al brazo real; abajo están la posición, los pulsos y las entradas/salidas en vivo.
- Pestaña **Conexión** → *Habilitar el mando* para mandar el brazo desde la ventana (con alguien junto a la
  seta de emergencia y el selector del panel en automático).
- Con el programa actual del PLC: *Iniciar* (homing o secuencia siguiente), *Detener*, *Paro de emergencia*,
  *Rearmar*. Con el programa `brazo_gemelo` (carpeta `plc` del repositorio): homing, mover a cualquier
  posición, secuencias, garra y velocidad.

Cada orden queda en `registro_gemelo.log`. El manual completo es `manual_gemelo_digital.pdf`.

## Contenido

| Archivo | Para qué |
|---|---|
| `gemelo_brazo.py` | Programa principal: servidor local, ventana y API |
| `brazo.py`, `ppi.py` | Comunicación con el PLC (PPI), perfiles de programa, estimador y PLC simulado |
| `ventana.py` | Ventana GTK + WebKit |
| `acceso.py`, `usuarios.py` | Usuarios, contraseñas y sesiones del acceso por red |
| `ui/` | Interfaz: visor 3D (three.js 0.160.0 incluido), estilos y modelo `brazo_xk-js1-1.glb` |
| `parametros.json` | Cotas y transmisión del brazo (copia de la cinemática del repositorio) |
| `empaquetar.py` | Solo dentro del repositorio: vuelve a copiar la interfaz y exporta esta carpeta |
