@echo off
echo Starting Care Intelligence...

start "Backend" cmd /k "cd /d "%~dp0backend" && venv310\Scripts\uvicorn app.main:app --port 8000"

timeout /t 3 /nobreak >nul

start "Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

timeout /t 5 /nobreak >nul

start http://localhost:5173
