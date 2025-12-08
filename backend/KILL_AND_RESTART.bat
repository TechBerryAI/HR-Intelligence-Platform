@echo off
echo ========================================
echo KILLING ALL PROCESSES ON PORT 3000
echo ========================================
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo Killing process %%a
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 3 /nobreak >nul
echo.
echo ========================================
echo STARTING FLASK SERVER
echo ========================================
cd /d %~dp0
python app.py

