@echo off
chcp 65001 >nul
title Motion Life - Setup
:: --- ask for administrator rights once ---
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
set "DEST=C:\MotionLife-Server"
echo.
echo   [1/5] Downloading Motion Life server...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://ywoywo12.github.io/motion-life/MotionLife-Server.zip' -OutFile \"$env:TEMP\ml.zip\"; Expand-Archive -Force \"$env:TEMP\ml.zip\" \"$env:TEMP\ml\"; New-Item -ItemType Directory -Force '%DEST%' | Out-Null; Copy-Item -Recurse -Force \"$env:TEMP\ml\MotionLife-Server\*\" '%DEST%'"
if not exist "%DEST%\server.js" ( echo   Download failed. Check the internet and try again. & pause & exit /b )
echo   [2/5] Checking Node.js...
where node >nul 2>nul
if errorlevel 1 (
  winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
  set "PATH=%PATH%;C:\Program Files\nodejs"
)
where node >nul 2>nul
if errorlevel 1 if not exist "C:\Program Files\nodejs\node.exe" ( echo   Please install Node.js LTS from https://nodejs.org then run this file again. & start "" https://nodejs.org/en/download & pause & exit /b )
echo   [3/5] Allowing the clinic devices through the firewall...
netsh advfirewall firewall delete rule name="Motion Life Server" >nul 2>&1
netsh advfirewall firewall add rule name="Motion Life Server" dir=in action=allow protocol=TCP localport=8080,8443 profile=any >nul
echo   [4/5] Auto-start with Windows...
set "SU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MotionLife-Server.bat"
> "%SU%" echo @echo off
>> "%SU%" echo cd /d "%DEST%"
>> "%SU%" echo start "Motion Life - Server" /min cmd /c "node server.js"
powercfg /change standby-timeout-ac 0 >nul 2>&1
echo   [5/5] Starting the server...
start "Motion Life - Server" /min cmd /c "cd /d "%DEST%" && node server.js"
timeout /t 3 >nul
start "" http://localhost:8080
echo.
echo   ==================================================
echo    Done. Open on the other devices (same Wi-Fi):
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { '      http://' + $_.IPAddress + ':8080' }"
echo   ==================================================
pause
