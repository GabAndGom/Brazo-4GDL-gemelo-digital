#!/bin/sh
# Crea los accesos "Gemelo digital del brazo" en el menu de aplicaciones (solo para este usuario).
# Para quitarlos:
#   rm ~/.local/share/applications/gemelo-brazo*.desktop
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/.local/share/applications"

crear() {  # archivo, nombre, opciones, terminal
  cat > "$HOME/.local/share/applications/$1.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$2
Comment=Visor 3D y mando del brazo XK-JS1-1 conectado al PLC S7-200
Exec="$DIR/iniciar_gemelo.sh"$3
Icon=$DIR/ui/icono.svg
Terminal=${4:-false}
Categories=Education;Engineering;
EOF
}

crear gemelo-brazo "Gemelo digital del brazo" ""
crear gemelo-brazo-simulado "Gemelo digital del brazo (simulado)" " --simulado"
# Con terminal: muestra la dirección para los celulares y los avisos (p. ej. si faltan usuarios)
crear gemelo-brazo-red "Gemelo digital del brazo (red local)" " --red" true
echo "Accesos creados en el menu de aplicaciones: busque 'Gemelo digital'."
