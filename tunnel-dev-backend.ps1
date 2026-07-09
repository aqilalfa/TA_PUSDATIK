# Jalankan Cloudflare Tunnel untuk SPBE Development - Backend
# Pastikan container backend sudah running:
#   docker_start.bat dev
#
# Script ini akan membuat quick tunnel ke backend http://localhost:8000
# dan menampilkan URL publik.

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logFile = "cloudflared-tunnel-backend-$stamp.log"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SPBE - Cloudflare Tunnel (Development Backend)            " -ForegroundColor Cyan
Write-Host "  Membuat tunnel ke http://localhost:8000 ...               " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Jalankan cloudflared
$proc = Start-Process -FilePath "cloudflared" -ArgumentList @(
    "--logfile", $logFile,
    "--loglevel", "info",
    "tunnel",
    "--url", "http://localhost:8000",
    "--no-autoupdate"
) -PassThru

Write-Host "PID: $($proc.Id)" -ForegroundColor Green
Write-Host "Log: $logFile" -ForegroundColor Green
Write-Host ""

# Tunggu tunnel siap
Start-Sleep -Seconds 8

# Baca URL dari log
$urlLine = Select-String -Path $logFile -Pattern "https://.*\.trycloudflare\.com" | Select-Object -First 1
if ($urlLine) {
    $url = $urlLine.Matches[0].Value
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host "  TUNNEL AKTIF (Backend)!                                   " -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host "  $url" -ForegroundColor White
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Tekan CTRL+C untuk menghentikan tunnel." -ForegroundColor Gray`n    Write-Host "PENTING: Untuk frontend dev, set VITE_API_URL ke URL ini lalu restart frontend." -ForegroundColor Yellow

    Write-Host "PENTING 2: Untuk backend, pastikan .trycloudflare.com diizinkan di CORS_ORIGINS backend!" -ForegroundColor Red

    # Test URL
    try {
        $r = Invoke-WebRequest -Uri "$url/api/health" -UseBasicParsing -TimeoutSec 10
        Write-Host "Status: $($r.StatusCode) OK" -ForegroundColor Green
    } catch {
        Write-Host "Status: menunggu siap... (bisa butuh beberapa detik)" -ForegroundColor Yellow
    }
} else {
    Write-Host "URL belum muncul. Cek log: Get-Content $logFile -Tail 5" -ForegroundColor Red
}

# Biarkan proses berjalan
Wait-Process -Id $proc.Id
