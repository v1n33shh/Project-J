@echo off
echo ==========================================
echo Jarvis OS - Stress Test Debug Launcher
echo ==========================================
echo.
echo Starting Backend Kernel with Debug Logging...
start "Jarvis Backend Terminal" cmd /k "cd C:\Users\Dizzyeyes\Desktop\jarvis_os && "C:\Users\Dizzyeyes\Desktop\Project J\.venv\Scripts\python.exe" run.py"

echo Starting React UI Dashboard...
cd C:\Users\Dizzyeyes\Desktop\jarvis_os\ui
npm run dev
