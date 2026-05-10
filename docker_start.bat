@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM  SPBE RAG System — Docker Launcher (auto-detect GPU)
REM  Usage:
REM    docker_start.bat dev        -> development (hot-reload)
REM    docker_start.bat prod       -> production
REM    docker_start.bat dev down   -> stop dev stack
REM    docker_start.bat prod down  -> stop prod stack
REM ============================================================

set "ENV=%~1"
set "ACTION=%~2"
if "%ACTION%"=="" set "ACTION=up"

REM --- Validasi argument ---
if /I "%ENV%"=="dev"  goto :begin
if /I "%ENV%"=="prod" goto :begin
echo.
echo  [ERROR] Argument tidak valid.
echo.
echo  Cara pakai:
echo    docker_start.bat dev         -- jalankan stack development
echo    docker_start.bat prod        -- jalankan stack production
echo    docker_start.bat dev  down   -- stop stack development
echo    docker_start.bat prod down   -- stop stack production
echo.
pause
exit /b 1

:begin
echo.
echo ============================================================
echo   SPBE RAG System ^| Mode: %ENV% ^| Action: %ACTION%
echo ============================================================

REM --- Pilih compose file utama ---
if /I "%ENV%"=="dev"  set "COMPOSE_MAIN=docker-compose.dev.yml"
if /I "%ENV%"=="prod" set "COMPOSE_MAIN=docker-compose.prod.yml"

REM --- Auto-detect GPU ---
set "HAS_GPU=0"
set "GPU_OVERRIDE="
nvidia-smi >nul 2>&1
if NOT errorlevel 1 (
    set "HAS_GPU=1"
    set "GPU_OVERRIDE=-f docker-compose.gpu.yml"
    echo   GPU: TERDETEKSI - stack akan berjalan dengan dukungan NVIDIA GPU
) else (
    echo   GPU: Tidak terdeteksi - stack akan berjalan dengan CPU saja
)

echo ============================================================
echo.

REM --- Jalankan docker compose ---
if /I "%ACTION%"=="down" (
    echo Menghentikan stack %ENV%...
    docker compose -f %COMPOSE_MAIN% %GPU_OVERRIDE% down
    echo.
    echo [OK] Stack %ENV% dihentikan.
    goto :end
)

if /I "%ACTION%"=="up" (
    echo Membangun dan menjalankan stack %ENV%...
    if /I "%ENV%"=="dev" (
        docker compose -f %COMPOSE_MAIN% %GPU_OVERRIDE% up --build
    ) else (
        docker compose -f %COMPOSE_MAIN% %GPU_OVERRIDE% up --build -d
        echo.
        echo [OK] Stack production berjalan di background.
        echo.
        echo   Frontend : http://localhost:80
        echo   Backend  : http://localhost:8000  (internal)
        echo   API Docs : http://localhost:8000/docs  (internal)
        echo.
        echo   Log: docker compose -f %COMPOSE_MAIN% %GPU_OVERRIDE% logs -f
        echo   Stop: docker_start.bat prod down
    )
    goto :end
)

echo [ERROR] Action tidak dikenal: %ACTION%
exit /b 1

:end
echo.
endlocal
