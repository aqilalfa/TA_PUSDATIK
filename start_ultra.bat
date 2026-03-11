@echo off
echo ============================================
echo SPBE RAG Chat - Ultra Lite (BM25 Only)
echo ============================================
echo.

cd /d D:\aqil\pusdatik\backend
call venv\Scripts\activate.bat

echo Starting server (NO embedding model = instant startup)
echo Server: http://localhost:8000
echo.

python -m uvicorn app.api.server_ultra:app --host 0.0.0.0 --port 8000
