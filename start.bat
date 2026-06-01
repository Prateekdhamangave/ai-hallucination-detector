@echo off
echo Starting AI Agent Evaluator...

:: Start Backend
start "Backend" cmd /k "cd /d %~dp0 && venv\Scripts\activate.bat && uvicorn app.main:app --reload"

:: Wait 5 seconds then start Frontend
timeout /t 5 /nobreak

:: Start Frontend
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo Both servers starting...
echo Backend: http://127.0.0.1:8000
echo Frontend: http://localhost:5173

:: Open browser after 5 more seconds
timeout /t 5 /nobreak
start http://localhost:5173