@echo off
setlocal EnableDelayedExpansion

set "BACKEND_PORT=8000"
if not defined BACKEND_HOST set "BACKEND_HOST=localhost"
if not defined FRONTEND_HOST set "FRONTEND_HOST=!BACKEND_HOST!"
set "BACKEND_URL=http://!BACKEND_HOST!:!BACKEND_PORT!"
set "FRONTEND_URL=http://!FRONTEND_HOST!:5173"
if not defined OLLAMA_BASE_URL set "OLLAMA_BASE_URL=http://localhost:11434"
if not defined CORS_ORIGINS set "CORS_ORIGINS=http://localhost,http://localhost:80,http://localhost:5173,http://localhost:3000"
if /I not "!BACKEND_HOST!"=="localhost" (
    set "CORS_ORIGINS=!CORS_ORIGINS!,http://!BACKEND_HOST!:5173"
)
set "BACKEND_HEALTH_URL=!BACKEND_URL!/api/health"
set "BACKEND_WAIT_SECONDS=8"
set "BACKEND_UP=0"
set "BACKEND_LAUNCHED=0"

echo ============================================
echo SPBE RAG Chat - Starting All Services
echo ============================================
echo.
echo This will open terminal windows for:
echo   1. Backend server (default port 8000)
echo   2. Frontend dev server (port 5173)
echo.
echo Make sure Docker (Qdrant) and Ollama are running!
echo ============================================
echo.

REM Check if Qdrant is running
echo Checking Qdrant...
curl -s --max-time 2 http://localhost:6333/collections > nul 2>&1
if errorlevel 1 (
    echo [WARNING] Qdrant not responding on port 6333
    echo          Run: docker start spbe-qdrant
) else (
    echo [OK] Qdrant is running
)

REM Check if Ollama is running
echo Checking Ollama...
curl -s --max-time 2 "%OLLAMA_BASE_URL%/api/tags" > nul 2>&1
if errorlevel 1 (
    echo [WARNING] Ollama not responding on port 11434
    echo          Run: ollama serve
) else (
    echo [OK] Ollama is running
)

echo.
echo Starting backend...

call :check_backend_health
if "!BACKEND_UP!"=="1" (
    echo [OK] Backend already running and healthy on port 8000
) else (
    set "PORT_8000_PID="
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do (
        if not defined PORT_8000_PID set "PORT_8000_PID=%%P"
    )

    if defined PORT_8000_PID (
        echo [WARNING] Port 8000 is used by PID !PORT_8000_PID! but backend health is not responding.
        echo [INFO] Trying fallback backend port 8001...

        set "BACKEND_PORT=8001"
        set "BACKEND_URL=http://!BACKEND_HOST!:!BACKEND_PORT!"
        set "BACKEND_HEALTH_URL=!BACKEND_URL!/api/health"

        call :check_backend_health
        if "!BACKEND_UP!"=="1" (
            echo [OK] Backend already running and healthy on fallback port !BACKEND_PORT!
        ) else (
            set "PORT_8001_PID="
            for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8001 .*LISTENING"') do (
                if not defined PORT_8001_PID set "PORT_8001_PID=%%P"
            )

            if defined PORT_8001_PID (
                echo [ERROR] Port 8001 also in use by PID !PORT_8001_PID!.
                echo         Free one backend port first, for example:
                echo         taskkill /PID !PORT_8000_PID! /F
                echo         taskkill /PID !PORT_8001_PID! /F
                echo         Then run start_all.bat again.
            ) else (
                call :start_backend
            )
        )
    ) else (
        call :start_backend
    )
)

echo.
echo Starting frontend...
start "SPBE Frontend" cmd /k "cd /d D:\aqil\pusdatik\frontend && set VITE_API_URL=!BACKEND_URL! && npm run dev"

if "!BACKEND_UP!"=="0" if "!BACKEND_LAUNCHED!"=="1" (
    echo [INFO] Frontend is starting now. Quick backend health check ^(max !BACKEND_WAIT_SECONDS!s^)...
    call :wait_backend !BACKEND_WAIT_SECONDS!
    if "!BACKEND_UP!"=="1" (
        echo [OK] Backend is healthy on !BACKEND_URL!
    ) else (
        echo [WARNING] Backend is still not healthy after quick check.
        echo           Frontend keeps running; check the "SPBE Backend" window for details.
    )
)

echo.
echo ============================================
if "!BACKEND_UP!"=="1" (
    echo Services started:
    echo   Backend:  !BACKEND_URL!
    echo   Frontend: !FRONTEND_URL!
    echo   API Docs: !BACKEND_URL!/docs
) else (
    echo Frontend started, but backend is not healthy yet.
    echo Resolve backend issue in "SPBE Backend" window, then retry.
)
echo ============================================
echo.
echo Close this window when done.
pause
exit /b

:check_backend_health
curl -s --max-time 3 "%BACKEND_HEALTH_URL%" > nul 2>&1
if errorlevel 1 (
    set "BACKEND_UP=0"
) else (
    set "BACKEND_UP=1"
)
exit /b

:start_backend
start "SPBE Backend" cmd /k "cd /d D:\aqil\pusdatik\backend && set CORS_ORIGINS=!CORS_ORIGINS! && set OLLAMA_BASE_URL=!OLLAMA_BASE_URL! && call venv\Scripts\activate.bat && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port !BACKEND_PORT!"
set "BACKEND_LAUNCHED=1"
exit /b

:wait_backend
set "BACKEND_UP=0"
set /a _max_wait=%~1
for /L %%I in (1,1,!_max_wait!) do (
    call :check_backend_health
    if "!BACKEND_UP!"=="1" exit /b 0
    ping -n 2 127.0.0.1 > nul
)
exit /b 1
