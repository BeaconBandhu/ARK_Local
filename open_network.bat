@echo off
echo ============================================================
echo  ARK -- Open Port 8000 for LAN access
echo  Right-clicked "Run as administrator"? Good. Continuing...
echo ============================================================
echo.

:: Step 1 -- Switch WiFi from Public to Private profile
:: (Public profile blocks all inbound connections by default)
echo [1/2] Setting WiFi network "SDM_LAB2" to Private profile...
powershell -Command "Set-NetConnectionProfile -Name 'SDM_LAB2' -NetworkCategory Private" 2>nul
if %errorlevel%==0 (
    echo       Done -- network is now Private.
) else (
    echo       Could not switch profile. Continuing with Public profile...
    echo       The firewall rule below will still cover Public networks.
)

echo.

:: Step 2 -- Add firewall rule for port 8000 on ALL profiles
echo [2/2] Creating inbound firewall rule for port 8000...
netsh advfirewall firewall delete rule name="ARK Backend Port 8000" >nul 2>&1
netsh advfirewall firewall add rule name="ARK Backend Port 8000" protocol=TCP dir=in localport=8000 action=allow profile=any

if %errorlevel%==0 (
    echo       Done -- firewall rule created.
) else (
    echo       ERROR: Could not create rule. Are you running as Administrator?
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  SUCCESS -- Other devices on the same WiFi can now access:
echo.
echo    Teacher Dashboard  :  http://10.13.231.31:8000/dashboard
echo    Student Portal     :  http://10.13.231.31:8000/student
echo    API Status Check   :  http://10.13.231.31:8000/api/status
echo.
echo  IP: 10.13.231.31  PORT: 8000  (locked -- do not change)
echo  "localhost" only works on THIS computer.
echo.
echo  If the IP above does not work, run ipconfig in a terminal
echo  and look for IPv4 Address under your Wi-Fi adapter.
echo ============================================================
echo.
pause
