@echo off
chcp 65001 >nul
title Library Seat Reservation System
echo ===================================================
echo   啟動圖書館座位預約系統 (MySQL + 學號登入版)...
echo ===================================================
py "%~dp0server.py"
if %errorlevel% neq 0 (
    python "%~dp0server.py"
)
if %errorlevel% neq 0 (
    "C:\Python314\python.exe" "%~dp0server.py"
)
pause
