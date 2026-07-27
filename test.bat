@echo on  
@echo off
setlocal EnableDelayedExpansion

echo ============================================
echo SPBE RAG Chat - Cloudflare Tunnel
echo ============================================
echo.

set "TOKEN="
if exist ".env.cloudflare" (
    for /f "tokens=1,* delims==" %%A in ('findstr /B "CLOUDFLARED_TUNNEL_TOKEN=" .env.cloudflare 2^>nul') do (
        set "TOKEN=%%B"
    )
)

if not "!TOKEN!"=="" (
    echo [INFO] Found Cloudflare Tunnel Token in .env.cloudflare.
    echo [INFO] Starting authenticated tunnel...
    echo.
    cloudflared tunnel --no-autoupdate run --token !TOKEN!
) else (
    echo [INFO] No token found in .env.cloudflare.
    echo [INFO] Starting Quick Tunnel for Frontend (port 5173)...
    echo.
    cloudflared tunnel --url http://localhost:5173
)

pause
