@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo No se encontro Python. Instalelo desde https://www.python.org/downloads/
  echo y marque la casilla "Add python.exe to PATH". Vea el manual de instalacion para Windows.
  pause
  exit /b 1
)
title Gemelo digital del brazo XK-JS1-1
echo Gemelo digital del brazo XK-JS1-1
echo Esta consola muestra la conexion con el PLC, los ingresos por red y las ordenes.
echo Para cerrar la app: cierre la ventana del gemelo o pulse Ctrl+C aqui.
echo.
%PY% gemelo_brazo.py %*
echo.
pause
