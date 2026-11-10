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
title Prueba de conexion con el PLC (solo lectura)
%PY% probar_plc.py %*
echo.
pause
