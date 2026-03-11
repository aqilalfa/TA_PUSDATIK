@echo off
echo ============================================
echo Download Reranker Model
echo ============================================
echo.
echo Model: BAAI/bge-reranker-v2-m3
echo Size: ~500MB
echo.
echo Pastikan koneksi internet stabil.
echo.

cd /d D:\aqil\pusdatik\backend
call venv\Scripts\activate.bat

python scripts\download_reranker.py

pause
