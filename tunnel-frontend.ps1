# Jalankan Cloudflare Tunnel untuk SPBE Frontend
# Pastikan container frontend sudah running:
#   docker start spbe-frontend-prod
#
# Script ini akan membuat quick tunnel ke http://localhost:80
# dan menampilkan URL publik.

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logFile = "cloudflared-tunnel-$stamp.log"

Write-Host "┌─────────────────────────────────────────────┐" -ForegroundColor Cyan
Write-Host "│  SPBE - Cloudflare Tunnel                   │" -ForegroundColor Cyan
Write-Host "│  Membuat tunnel ke http://localhost:80 ...   │" -ForegroundColor Cyan
Write-Host "└─────────────────────────────────────────────┘" -ForegroundColor Cyan
Write-Host ""

# Jalankan cloudflared
$proc = Start-Process -FilePath "cloudflared" -ArgumentList @(
    "--logfile", $logFile,
    "--loglevel", "info",
    "tunnel",
    "--url", "http://localhost:80",
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
    Write-Host "┌─────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "│  TUNNEL AKTIF!                              │" -ForegroundColor Yellow
    Write-Host "├─────────────────────────────────────────────┤" -ForegroundColor Yellow
    Write-Host "│  $url" -ForegroundColor White
    Write-Host "└─────────────────────────────────────────────┘" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Tekan CTRL+C untuk menghentikan tunnel." -ForegroundColor Gray

    # Test URL
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
        Write-Host "Status: $($r.StatusCode) OK" -ForegroundColor Green
    } catch {
        Write-Host "Status: menunggu siap... (bisa butuh beberapa detik)" -ForegroundColor Yellow
    }
} else {
    Write-Host "URL belum muncul. Cek log: Get-Content $logFile -Tail 5" -ForegroundColor Red
}

# Biarkan proses berjalan
Wait-Process -Id $proc.Id
