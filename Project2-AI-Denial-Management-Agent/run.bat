@echo off
setlocal

set ROOT=%~dp0
set BACKEND=%ROOT%backend
set FRONTEND=%ROOT%frontend

if not exist "%BACKEND%\venv\Scripts\python.exe" (
    echo Creating backend virtual environment...
    python -m venv "%BACKEND%\venv"
    call "%BACKEND%\venv\Scripts\pip.exe" install -q -r "%BACKEND%\requirements.txt"
)

if not exist "%FRONTEND%\node_modules" (
    echo Installing frontend dependencies...
    call npm install --prefix "%FRONTEND%"
)

echo Starting backend on http://localhost:8000 ...
start "Denial Management Agent - Backend" cmd /k "cd /d "%BACKEND%" && venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"

echo Starting frontend on http://localhost:5173 ...
start "Denial Management Agent - Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev"

echo.
echo Both services are starting in separate windows.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
