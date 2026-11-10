#!/bin/sh
# Abre la app del gemelo digital del brazo XK-JS1-1: primero el menu de modos.
# Opciones (opcionales): --modo simulacion|local|red, --puerto /dev/ttyUSB0, --navegador
cd "$(dirname "$0")" && exec python3 gemelo_brazo.py "$@"
