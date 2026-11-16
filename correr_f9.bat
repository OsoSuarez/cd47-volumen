@echo off
chcp 65001 >nul
cd /d C:\Users\jorge.suarez\cd47-volumen
set F9_HEADLESS=0
set F9_CHANNEL=chrome
set F9_PERFIL=C:\Users\jorge.suarez\f9_perfil
echo === Bot Fountain9: bajando planes (tarda ~20 min) ===
python fountain9\run_planes.py
echo.
echo === Termino. Si dice LOGIN FALLIDO o un error, mandale captura a Claude ===
pause
