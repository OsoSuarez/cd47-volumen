@echo off
chcp 65001 >nul
cd /d C:\Users\jorge.suarez\cd47-volumen
echo === Servidor del boton "Ejecutar bot" (puerto 9748). Dejalo abierto. ===
python fountain9\servidor_bot.py
pause
