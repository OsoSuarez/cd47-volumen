@echo off
chcp 65001 >nul
echo Instalando el servidor del boton "Ejecutar bot" en el inicio de Windows (sin permisos de admin)...
set "ST=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
> "%ST%\servidor_bot_cd47.vbs" echo CreateObject("WScript.Shell").Run "cmd /c cd /d C:\Users\jorge.suarez\cd47-volumen && pythonw fountain9\servidor_bot.py", 0, False
if exist "%ST%\servidor_bot_cd47.vbs" (
  echo OK: instalado. Desde el proximo inicio de sesion el servidor se prende solo.
  echo Para prenderlo ahora sin reiniciar, ejecuta servidor_bot.bat
) else (
  echo ERROR: no se pudo crear el archivo en %ST%
)
pause
