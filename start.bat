@echo off
title ARK Launcher
set NODE="C:\Program Files\nodejs\node.exe"
set NPX="C:\Program Files\nodejs\npx.cmd"

echo ================================================
echo   ARK - Starting all services
echo ================================================
echo.

echo [1/2] Starting ARK backend on port 8000...
start "ARK Backend" cmd /k "cd /d C:\Users\Aranya\Pictures\ARK\backend && python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [2/2] Starting student mobile app (Expo)...
start "ARK Student App" cmd /k "cd /d C:\Users\Aranya\Pictures\ARK\mobile && %NPX% expo start --tunnel"

timeout /t 5 /nobreak >nul

echo Opening teacher dashboard...
start "" "http://10.13.231.31:8000/dashboard"

echo.
echo ================================================
echo   ARK is running!
echo.
echo   Teacher dashboard : http://10.13.231.31:8000/dashboard
echo   Student portal    : http://10.13.231.31:8000/student
echo   Student mobile    : Scan QR in the Expo window
echo                       with Expo Go app on phone
echo.
echo   Server IP : 10.13.231.31   PORT : 8000  (locked)
echo ================================================
pause
