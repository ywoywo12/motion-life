@echo off
chcp 65001 >nul
title Motion Life - Fix network access
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
echo.
echo   [1/4] Removing Windows rules that BLOCK the server...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetFirewallApplicationFilter | Where-Object { $_.Program -like '*node.exe' } | Get-NetFirewallRule | Where-Object { $_.Action -eq 'Block' } | ForEach-Object { Write-Host ('      removed: ' + $_.DisplayName + ' / ' + $_.Profile); Remove-NetFirewallRule -Name $_.Name }"
echo   [2/4] Allowing the server on ALL network types (with or without internet)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$n=(Get-Command node -ErrorAction SilentlyContinue).Source; if(-not $n){$n='C:\Program Files\nodejs\node.exe'}; Remove-NetFirewallRule -DisplayName 'Motion Life Node' -ErrorAction SilentlyContinue; New-NetFirewallRule -DisplayName 'Motion Life Node' -Direction Inbound -Program $n -Action Allow -Profile Any | Out-Null; Remove-NetFirewallRule -DisplayName 'Motion Life Server' -ErrorAction SilentlyContinue; New-NetFirewallRule -DisplayName 'Motion Life Server' -Direction Inbound -Protocol TCP -LocalPort 8080,8443 -Action Allow -Profile Any | Out-Null; Write-Host '      done.'"
echo   [3/4] Marking the clinic network as Private...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -ne 'DomainAuthenticated' } | ForEach-Object { try { Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private; Write-Host ('      ' + $_.InterfaceAlias + ' -> Private') } catch {} }"
echo   [4/4] Current addresses of this laptop:
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.168.*' } | ForEach-Object { '      https://' + $_.IPAddress + ':8443   (' + $_.InterfaceAlias + ')' }"
echo.
echo   Finished. Now try the link on a tablet.
pause
