@echo off
setlocal

REM Start the local Firestore emulator and Firebase Emulator UI.
REM Authentication remains connected to Firebase cloud; only Firestore runs locally.
if exist "%APPDATA%\npm\firebase.cmd" (
  set "FIREBASE_CLI=%APPDATA%\npm\firebase.cmd"
) else (
  where firebase.cmd >nul 2>nul
  if errorlevel 1 (
    echo Firebase CLI was not found.
    echo Install it with: npm install -g firebase-tools
    pause
    exit /b 1
  )
  set "FIREBASE_CLI=firebase.cmd"
)
start "Vendly Firestore" cmd /k "cd /d ""%~dp0"" && ""%FIREBASE_CLI%"" emulators:start --only firestore --import "".\emulator-data"""

REM Start the Flask backend in its own terminal window.
if exist "%~dp0backend\.venv\Scripts\python.exe" (
  set "BACKEND_PYTHON=%~dp0backend\.venv\Scripts\python.exe"
) else (
  set "BACKEND_PYTHON=python"
)
start "Vendly Backend" cmd /k "cd /d ""%~dp0backend"" && set ""FIRESTORE_EMULATOR_HOST=127.0.0.1:8080"" && ""%BACKEND_PYTHON%"" run.py"

REM Start the Vite frontend in its own terminal window.
REM --host allows another device on the same Wi-Fi network to open the site.
start "Vendly Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev -- --host"

echo Vendly Firestore, backend and frontend are starting...
echo Firestore: 127.0.0.1:8080
echo Emulator UI: http://127.0.0.1:4000
echo Backend:  http://127.0.0.1:5000
echo Frontend: http://localhost:5173
echo Network:  use your computer IP, for example http://192.168.1.2:5173

endlocal
