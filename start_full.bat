@echo off
echo ============================================
echo SPBE RAG Chat - Full Server v4.0
echo ============================================
echo.
echo Features:
echo   - Local embedding model (indo-sentence-bert-base)
echo   - BM25 + Vector hybrid search
echo   - Cross-encoder reranker (bge-reranker-v2-m3)
echo   - Parent Document Retrieval (full Pasal context)
echo   - RRF fusion for best results
echo.
echo Pipeline: BM25 + Vector -^> Rerank -^> Parent Expansion -^> LLM
echo.
echo NOTE: First run will download reranker model (~500MB)
echo       Subsequent runs are faster.
echo.

cd /d D:\aqil\pusdatik\backend
call venv\Scripts\activate.bat

echo Starting server...
echo Server: http://localhost:8000
echo Frontend: http://localhost:5173
echo Health check: http://localhost:8000/api/health
echo.

python -m uvicorn app.api.server_full:app --host 0.0.0.0 --port 8000
