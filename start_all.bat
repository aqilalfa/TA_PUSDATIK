@echo off
echo ============================================
echo SPBE RAG Chat - Starting All Services
echo ============================================
echo.
echo This will open two terminal windows:
echo   1. Backend server (port 8000)
echo   2. Frontend dev server (port 5173)
echo.
echo Make sure Docker (Qdrant) and Ollama are running!
echo ============================================
echo.

REM Check if Qdrant is running
echo Checking Qdrant...
curl -s http://localhost:6333/collections > nul 2>&1
if errorlevel 1 (
    echo [WARNING] Qdrant not responding on port 6333
    echo Run: docker start spbe-qdrant
) else (
    echo [OK] Qdrant is running
)

REM Check if Ollama is running
echo Checking Ollama...
curl -s http://localhost:11434/api/tags > nul 2>&1
if errorlevel 1 (
    echo [WARNING] Ollama not responding on port 11434
    echo Run: ollama serve
) else (
    echo [OK] Ollama is running
)

echo.
echo Starting services...

REM Start backend in new window
start "SPBE Backend" cmd /k "cd /d D:\aqil\pusdatik\backend && call venv\Scripts\activate.bat && python -m uvicorn app.api.server:app --host 0.0.0.0 --port 8000 --reload"

REM Wait a bit for backend to start
timeout /t 3 /nobreak > nul

REM Start frontend in new window  
start "SPBE Frontend" cmd /k "cd /d D:\aqil\pusdatik\frontend && npm run dev"

echo.
echo ============================================
echo Services starting...
echo   Backend: http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://localhost:8000/docs
echo ============================================
echo.
echo Close this window when done.
pause
