@echo off
title Start All - Airfare Price Index
echo Starting both Backend and Frontend...

start "Backend Server" cmd /c "backend_start.cmd"
timeout /t 3 /nobreak > nul

start "Frontend Server" cmd /c "Frontend_start.cmd"
echo.
echo Servers are starting in new windows.
echo Frontend: http://localhost:5173
echo Backend API: http://127.0.0.1:8000
echo.
pause
