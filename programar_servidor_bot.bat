@echo off
chcp 65001 >nul
echo Programando el servidor del boton "Ejecutar bot": se inicia solo al abrir sesion en Windows...
schtasks /Create /TN "Servidor Bot F9 CD47" /TR "pythonw C:\Users\jorge.suarez\cd47-volumen\fountain9\servidor_bot.py" /SC ONLOGON /RL LIMITED /F
echo.
echo Listo. Desde la proxima vez que inicies sesion el boton funciona solo. Para usarlo ahora, ejecuta servidor_bot.bat
pause
