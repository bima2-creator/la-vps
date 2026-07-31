@echo off
setlocal
title LA Tracker - Update / Rebuild
cd /d "%~dp0"

echo ============================================
echo   Rebuild LA Tracker (setelah update kode)
echo ============================================
docker compose down
docker compose build --no-cache
docker compose up -d
echo.
echo [i] Rebuild selesai. Buka http://localhost:3000
pause
endlocal
