# Gemelo digital del brazo XK-JS1-1 (app en Python)

La app conecta la PC con el PLC S7-200 del brazo por el cable USB-PPI y muestra el brazo real en
el visor 3D de la página. Si el programa del PLC lo permite, también lo mueve desde la página.
El manual completo está en [manual_gemelo_digital.pdf](manual/manual_gemelo_digital.pdf).

```
PLC S7-200 (puerto 0, PPI) ⇄ cable USB-PPI (/dev/ttyUSB0) ⇄ app gemelo_brazo.py ⇄ navegador (localhost:8050)
```

## App de escritorio

La carpeta `app/` es una aplicación autónoma: solo el gemelo del brazo, con ventana propia (GTK + WebKit),
three.js incluido (funciona sin internet) y su copia del modelo y de la cinemática. Para llevarla a otra PC:

```bash
cd semestres/2026_II/gemelo-digital/app
python3 empaquetar.py --destino ~/gemelo_brazo_app     # carpeta + gemelo_brazo_app.zip
~/gemelo_brazo_app/instalar_acceso.sh                  # accesos en el menú de aplicaciones
```

En la PC del laboratorio ya quedó en `ETN 1034/gemelo_brazo_app` con sus accesos
"Gemelo digital del brazo" y "Gemelo digital del brazo (simulado)" en el menú.

## Arranque rápido

1. Enchufe el cable USB-PPI al puerto 0 del PLC y a la PC. En VirtualBox, el USB **no** debe estar
   tomado por la máquina virtual (menú Dispositivos → USB → desmarcar "USB2.0-Serial").
2. En una terminal:

   ```bash
   cd semestres/2026_II/gemelo-digital/app
   python3 gemelo_brazo.py
   ```

   La app busca el PLC (dirección PPI 6 a 19.2 kbit/s), reconoce el programa cargado y abre su
   ventana (con `--navegador`, en el navegador: `http://localhost:8050/`). Sin PLC se puede practicar con `python3 gemelo_brazo.py --simulado`.
3. En la ventana, el modelo 3D sigue al brazo real. En la pestaña **Conexión** está el
   estado del PLC y la casilla **Habilitar el mando**: solo con ella marcada la página puede mover el brazo.

No hace falta instalar nada: la app usa solo la biblioteca estándar de Python 3.

## Acceso desde celulares y otras PC de la red local (con contraseña)

1. Cree los usuarios en la PC del laboratorio (la contraseña se pide sin mostrarla):

   ```bash
   cd semestres/2026_II/gemelo-digital/app
   python3 usuarios.py agregar ana --rol operador
   python3 usuarios.py agregar visita --rol observador
   ```

   - **observador**: ve el brazo en vivo (posición, E/S) y la simulación; no puede mandarlo.
   - **operador**: además lo manda. Un solo operador tiene el mando a la vez; los demás ven quién lo tiene
     y pueden dar **paro**. Al salir o tras 8 h sin uso, el mando se suelta solo.
2. Abra la app en modo red: menú **Gemelo digital del brazo (red local)** o `./iniciar_gemelo.sh --red`.
   La terminal muestra la dirección, por ejemplo `https://192.168.1.15:8443/`.
3. En el celular (misma red Wi-Fi) abra esa dirección. La primera vez el navegador avisa que el certificado
   no es de una autoridad: es el certificado propio del laboratorio; elija continuar. Ingrese con su usuario.

Si el celular no llega a la página, el cortafuegos de la PC puede estar bloqueando el puerto: hay que
permitirlo una vez con `sudo ufw allow 8443/tcp` (lo hace quien administra la PC).

La ventana de la PC del laboratorio sigue sin contraseña (quien está ahí está en la planta); con
`--clave-local` también la pide. Usuarios, contraseñas (cifradas con PBKDF2) y certificado quedan en
`usuarios.json` y `tls_*.pem` dentro de la carpeta de la app: no se suben al repositorio.

## Qué se puede hacer según el programa del PLC

| Programa en el PLC | Ver el brazo en vivo | Mandar desde la página |
|---|---|---|
| Programa actual (secuencias, cargado el 26/10/2026) | Sí, con la posición **estimada** a partir de los pulsos | Iniciar (homing o secuencia siguiente), Detener, Paro de emergencia, Rearmar |
| `plc/brazo_gemelo.awl` (este proyecto) | Sí, con la posición **contada en el PLC** | Homing, mover a cualquier posición (articular o cartesiana), secuencias grabadas, garra, velocidad |
| Otro programa | Sí (solo entradas, salidas y posición estimada) | No |

Para mover a voluntad hay que cargar `plc/brazo_gemelo.mwp` en el PLC (instrucciones en el manual,
sección "Cargar el programa del gemelo en el PLC"). El programa anterior quedó respaldado en `ETN 1034/respaldo_vm/programa_plc_cargado_20261026.mwp`.

## Seguridad

- Siempre una persona junto a la seta de emergencia del tablero mientras la PC tenga el mando.
- El selector del panel (I0.5) manda: en **manual** el brazo solo obedece al panel; la PC necesita **automático**.
- Si la app o la página se cierran, el PLC detiene el movimiento solo: el programa del gemelo tiene un
  watchdog de 2 s y el programa actual borra las órdenes de la PC a los 5 s.
- Toda orden de la PC queda registrada en `app/registro_gemelo.log`.

## Archivos

| Archivo | Contenido |
|---|---|
| `app/gemelo_brazo.py` | La app: servidor de la página y API (`/api/estado`, `/api/orden/...`) |
| `app/brazo.py` | Perfiles de cada programa del PLC, estimador de posición y PLC simulado |
| `app/ppi.py` | Cliente PPI (lectura y escritura de memoria del S7-200, sin dependencias) |
| `plc/brazo_gemelo.awl`, `plc/brazo_gemelo.mwp` | Programa del PLC para el gemelo digital (compilado sin errores en Micro/WIN 4.0) |
| `manual/manual_gemelo_digital.tex`, `.pdf` | Manual de conexión y uso |
