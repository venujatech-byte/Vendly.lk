@echo off
setlocal

REM Start the Flask backend in its own terminal window.
if exist "%~dp0backend\.venv\Scripts\python.exe" (
  set "BACKEND_PYTHON=%~dp0backend\.venv\Scripts\python.exe"
) else (
  set "BACKEND_PYTHON=python"
)
start "Vendly Backend" cmd /k "cd /d "%~dp0backend" && "%BACKEND_PYTHON%" run.py"

REM Start the Vite frontend in its own terminal window.
REM --host allows another device on the same Wi-Fi network to open the site.
start "Vendly Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev -- --host"

echo Vendly backend and frontend are starting...
echo Backend:  http://127.0.0.1:5000
echo Frontend: http://localhost:5173
echo Network:  use your computer IP, for example http://192.168.1.2:5173

endlocal
