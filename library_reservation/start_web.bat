@echo off
title Library Seat Reservation System
echo Starting Library Reservation Web System...
echo Please wait...
py "%~dp0server.py"
if %errorlevel% neq 0 (
    echo.
    echo Retrying with direct Python path...
    "C:\Python314\python.exe" "%~dp0server.py"
)
pause
