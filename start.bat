@echo off
setlocal enabledelayedexpansion
title LA Tracker - Start
cd /d "%~dp0"

echo ============================================
echo   LA Tracker - Local Start (Windows)
echo ============================================
echo.

REM ---- 1. Cek Docker Desktop ----
docker version >nul 2>&1
if errorlevel 1 (
    echo [X] Docker Desktop belum berjalan atau belum terinstall.
    echo     Silakan buka Docker Desktop terlebih dahulu, lalu jalankan ulang start.bat
    echo     Download: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

REM ---- 2. Cek docker compose (v2 subcommand) ----
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [X] Perintah "docker compose" tidak tersedia. Update Docker Desktop ke versi terbaru.
    pause
    exit /b 1
)

REM ---- 3. Siapkan local.env jika belum ada ----
if not exist "local.env" (
    echo [i] local.env belum ada, membuat dari local.env.example ...
    copy /y local.env.example local.env >nul
    echo [i] local.env dibuat. Silakan edit ADMIN_EMAIL / ADMIN_PASSWORD / JWT_SECRET bila perlu.
)

REM ---- 4. Siapkan folder data (persistent) ----
if not exist "data" mkdir data
if not exist "data\mongo" mkdir data\mongo
if not exist "data\attachments" mkdir data\attachments

REM ---- 5. Build (kalau image belum ada) dan Start ----
echo.
echo [i] Building images (hanya lama saat pertama kali) ...
docker compose build
if errorlevel 1 (
    echo [X] Build gagal. Lihat pesan error di atas.
    pause
    exit /b 1
)

echo.
echo [i] Menjalankan container di background ...
docker compose up -d
if errorlevel 1 (
    echo [X] Gagal menjalankan container.
    pause
    exit /b 1
)

REM ---- 6. Tunggu backend siap ----
echo.
echo [i] Menunggu backend siap ...
set /a tries=0
:waitloop
set /a tries+=1
docker compose exec -T backend curl -sf http://127.0.0.1:8001/api/ >nul 2>&1
if not errorlevel 1 goto ready
if !tries! GEQ 30 goto ready
timeout /t 2 /nobreak >nul
goto waitloop
:ready

REM ---- 7. Deteksi IP LAN ----
set "LANIP="
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /r /c:"IPv4"') do (
    if not defined LANIP (
        for /f "tokens=* delims= " %%B in ("%%A") do set "LANIP=%%B"
    )
)

echo.
echo ============================================
echo   LA Tracker sudah berjalan!
echo ============================================
echo   Akses lokal (PC ini)     : http://localhost:3000
if defined LANIP echo   Akses dari LAN/WiFi     : http://!LANIP!:3000
echo.
echo   Login default (pakai USERNAME, bukan email):
echo     Username : admin      Password : admin123   (Administrator)
echo     Username : operator   Password : operator   (Operator)
echo     Username : guest      Password : guest      (Viewer/lihat saja)
echo   (password bisa diubah di file local.env)
echo.
echo   Perintah berguna:
echo     stop.bat        - matikan semua service
echo     docker compose logs -f      - lihat log realtime
echo ============================================
echo.

REM ---- 8. Buka browser otomatis ----
start "" "http://localhost:3000"

pause
endlocal
