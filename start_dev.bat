@echo off
echo ============================================================
echo SPBE RAG Chat System - Development Server
echo ============================================================
echo.
echo Starting both backend and frontend servers...
echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Press Ctrl+C to stop both servers
echo ============================================================
echo.

REM Start backend in new window
start "SPBE RAG Backend" cmd /k "cd /d D:\aqil\pusdatik\backend && .\venv\Scripts\activate && python -m uvicorn app.api.chat_server:app --reload --port 8000"

REM Wait for backend to start
timeout /t 5 /nobreak

REM Start frontend in new window
start "SPBE RAG Frontend" cmd /k "cd /d D:\aqil\pusdatik\frontend && npm run dev"

echo.
echo Servers started! Open http://localhost:5173 in your browser.
echo.
pause
