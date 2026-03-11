@echo off
echo ============================================
echo SPBE RAG Chat - Hybrid Server v2.0
echo ============================================
echo.
echo Features:
echo   - BM25 search with regulation boosting
echo   - Strict citation prompting
echo   - Fast startup (no embedding model load)
echo.

cd /d D:\aqil\pusdatik\backend
call venv\Scripts\activate.bat

echo Starting server...
echo Server: http://localhost:8000
echo Frontend: http://localhost:5173
echo.

python -m uvicorn app.api.server_hybrid:app --host 0.0.0.0 --port 8000
