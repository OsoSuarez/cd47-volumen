@echo off
chcp 65001 >nul
echo Programando el bot de Fountain9: lunes a viernes 10:00...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$a = New-ScheduledTaskAction -Execute 'C:\Users\jorge.suarez\cd47-volumen\correr_f9.bat' -WorkingDirectory 'C:\Users\jorge.suarez\cd47-volumen'; $t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 10:00; $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2); Register-ScheduledTask -TaskName 'Bot Fountain9 CD47' -Action $a -Trigger $t -Settings $s -Description 'Baja los planes de Fountain9 y actualiza el tablero cd47-volumen' -Force | Out-Null; Get-ScheduledTask -TaskName 'Bot Fountain9 CD47' | Select-Object TaskName,State | Format-Table"
echo.
echo Listo. Se ve en el Programador de tareas como "Bot Fountain9 CD47".
pause
