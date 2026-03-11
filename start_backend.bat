@echo off
echo ============================================
echo SPBE RAG Chat - Starting Services
echo ============================================
echo.

REM Change to backend directory
cd /d D:\aqil\pusdatik\backend

REM Activate virtual environment
call venv\Scripts\activate.bat

echo Starting backend server...
echo Server: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop
echo ============================================

python -m uvicorn app.api.server:app --host 0.0.0.0 --port 8000 --reload
