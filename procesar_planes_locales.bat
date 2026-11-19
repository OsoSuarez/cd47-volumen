@echo off
chcp 65001 >nul
cd /d C:\Users\jorge.suarez\cd47-volumen
echo === Usando los 2 planes que dejaste en descargas (sin entrar a Fountain9) ===
set F9_SOLO_LOCAL=1
python fountain9\run_planes.py
echo.
echo === Termino. Si dice LOGIN FALLIDO o un error, mandale captura a Claude ===
pause
