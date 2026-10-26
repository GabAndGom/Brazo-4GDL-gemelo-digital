#!/bin/sh
# Abre la app del gemelo digital del brazo XK-JS1-1 (ventana propia).
# Opciones: --simulado (sin PLC), --direccion 6, --puerto /dev/ttyUSB0, --navegador
cd "$(dirname "$0")" && exec python3 gemelo_brazo.py "$@"
