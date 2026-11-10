@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Creando el acceso directo en el escritorio...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d = [Environment]::GetFolderPath('Desktop'); $w = New-Object -ComObject WScript.Shell; $c = (Get-Location).Path;" ^
  "$l = $w.CreateShortcut((Join-Path $d 'Gemelo digital del brazo.lnk')); $l.TargetPath = (Join-Path $c 'Gemelo digital.bat');" ^
  "$l.WorkingDirectory = $c; $l.IconLocation = (Join-Path $c 'icono.ico'); $l.Save()"
echo Listo: busque "Gemelo digital del brazo" en el escritorio.
pause
