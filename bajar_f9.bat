@echo off
chcp 65001 >nul
cd /d C:\Users\jorge.suarez\cd47-volumen
set F9_HEADLESS=0
set F9_CHANNEL=chrome
set F9_PERFIL=C:\Users\jorge.suarez\f9_perfil
set F9_SOLO_BAJAR=1
echo === Bot Fountain9: SOLO BAJAR los 2 ultimos planes (ya creados) ===
python fountain9\run_planes.py
echo.
echo === Termino. Si hay lineas en rojo, mandale captura a Claude ===
pause
