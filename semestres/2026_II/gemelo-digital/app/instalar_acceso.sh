#!/bin/sh
# Crea el acceso "Gemelo digital del brazo" en el menu de aplicaciones (solo para este usuario).
# La app abre un menu con los tres modos: simulacion, operacion local y operacion por red local.
# Para quitarlo:
#   rm ~/.local/share/applications/gemelo-brazo*.desktop
DIR="$(cd "$(dirname "$0")" && pwd)"
APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
# accesos de versiones anteriores (uno por modo): ya no hacen falta
rm -f "$APPS/gemelo-brazo-simulado.desktop" "$APPS/gemelo-brazo-red.desktop" "$APPS/gemelo-brazo-red-simulado.desktop"
# Con terminal: muestra la conexion con el PLC, los ingresos por red y las ordenes
cat > "$APPS/gemelo-brazo.desktop" <<FIN
[Desktop Entry]
Type=Application
Name=Gemelo digital del brazo
Comment=Simulacion, operacion local y por red del brazo XK-JS1-1 (PLC S7-200)
Exec="$DIR/iniciar_gemelo.sh"
Icon=$DIR/ui/icono.svg
Terminal=true
Categories=Education;Engineering;
FIN
chmod +x "$DIR/iniciar_gemelo.sh"
echo "Acceso creado en el menu de aplicaciones: busque 'Gemelo digital del brazo'."
