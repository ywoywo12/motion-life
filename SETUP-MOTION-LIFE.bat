@echo off
chcp 65001 >nul
title Motion Life - Setup / Update
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
set "DEST=C:\MotionLife-Server"
echo.
echo   [1/6] Stopping the old server (if running)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'node.exe' -and $_.CommandLine -like '*server.js*') -or $_.Name -eq 'whisper-server.exe' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo   [2/6] Downloading the latest Motion Life (your data is kept)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://ywoywo12.github.io/motion-life/MotionLife-Server.zip' -OutFile \"$env:TEMP\ml.zip\"; Remove-Item -Recurse -Force \"$env:TEMP\ml\" -ErrorAction SilentlyContinue; Expand-Archive -Force \"$env:TEMP\ml.zip\" \"$env:TEMP\ml\"; New-Item -ItemType Directory -Force '%DEST%' | Out-Null; Copy-Item -Recurse -Force \"$env:TEMP\ml\MotionLife-Server\*\" '%DEST%'"
if not exist "%DEST%\server.js" ( echo   Download failed. Check the internet and try again. & pause & exit /b )
echo   [3/6] Checking Node.js...
where node >nul 2>nul
if errorlevel 1 (
  winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
  set "PATH=%PATH%;C:\Program Files\nodejs"
)
echo   [4/6] Offline voice-to-text engine (one time, about 550 MB - please wait)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEST%\stt-install.ps1" -Dest "%DEST%"
echo   [5/6] Firewall + auto-start...
netsh advfirewall firewall delete rule name="Motion Life Server" >nul 2>&1
netsh advfirewall firewall add rule name="Motion Life Server" dir=in action=allow protocol=TCP localport=8080,8443 profile=any >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetFirewallApplicationFilter | Where-Object { $_.Program -like '*node.exe' } | Get-NetFirewallRule | Where-Object { $_.Action -eq 'Block' } | Remove-NetFirewallRule; $n=(Get-Command node -ErrorAction SilentlyContinue).Source; if(-not $n){$n='C:\Program Files\nodejs\node.exe'}; Remove-NetFirewallRule -DisplayName 'Motion Life Node' -ErrorAction SilentlyContinue; New-NetFirewallRule -DisplayName 'Motion Life Node' -Direction Inbound -Program $n -Action Allow -Profile Any | Out-Null; Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -ne 'DomainAuthenticated' } | ForEach-Object { try { Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private } catch {} }"
set "SU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MotionLife-Server.bat"
> "%SU%" echo @echo off
>> "%SU%" echo cd /d "%DEST%"
>> "%SU%" echo start "Motion Life - Server" /min cmd /c "node server.js"
powercfg /change standby-timeout-ac 0 >nul 2>&1
echo   [6/6] Starting the server...
start "Motion Life - Server" /min cmd /c "cd /d "%DEST%" && node server.js"
timeout /t 4 >nul
start "" http://localhost:8080
echo.
echo   ==================================================
echo    Done. On the other devices (same Wi-Fi) open:
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.168.*' -or $_.IPAddress -like '10.*' -or $_.IPAddress -like '172.*' } | ForEach-Object { '      https://' + $_.IPAddress + ':8443' }"
echo   ==================================================
pause
