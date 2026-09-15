@echo off
chcp 65001 > nul
echo 正在啟動圖書館座位預約系統...
py "%~dp0main.py"
if %errorlevel% neq 0 (
    python "%~dp0main.py"
)
pause
