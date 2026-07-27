@echo off
setlocal EnableDelayedExpansion

echo ============================================
echo SPBE RAG Chat - Cloudflare Tunnel
echo ============================================
echo.

set "TOKEN="
if not exist ".env.cloudflare" goto check_token

for /f "tokens=1,* delims==" %%A in ('findstr /B "CLOUDFLARED_TUNNEL_TOKEN=" .env.cloudflare 2^>nul') do set "TOKEN=%%B"

:check_token
if "!TOKEN!"=="" goto run_quick

echo [INFO] Token Cloudflare ditemukan di .env.cloudflare
echo.
echo Pilih mode Tunnel yang ingin dijalankan:
echo 1. Authenticated Tunnel (Gunakan token, terhubung ke domain Cloudflare Zero Trust Anda)
echo 2. Quick Tunnel (Tanpa token, dapatkan tautan acak .trycloudflare.com)
echo.
set /p "CHOICE=Masukkan pilihan (1/2): "

if "!CHOICE!"=="2" goto run_quick
goto run_auth

:run_auth
echo.
echo [INFO] Memulai Authenticated tunnel...
echo [INFO] Akses aplikasi melalui domain yang sudah di-set di dashboard Cloudflare Anda.
echo.
cloudflared tunnel --no-autoupdate run --token !TOKEN!
goto end

:run_quick
echo.
echo [INFO] Memulai Quick Tunnel untuk Frontend (port 5173)...
echo [INFO] Troubleshooting: Jika muncul Error 1101 / 500 Internal Server Error,
echo [INFO] itu berarti server Cloudflare terdekat sedang gangguan untuk tunnel gratis.
echo.
cloudflared tunnel --url http://localhost:5173

echo.
echo [WARNING] Quick tunnel gagal atau terputus!
set /p "RETRY=Ingin mencoba ulang dengan rute server Amerika (US)? (Y/N): "
if /I not "!RETRY!"=="Y" goto end

echo.
echo [INFO] Mencoba rute server US (--region us) ...
cloudflared tunnel --url http://localhost:5173 --region us
goto end

:end
pause
