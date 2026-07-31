@echo off
setlocal
title LA Tracker - Backup Data
cd /d "%~dp0"

echo ============================================
echo   Backup data LA Tracker (MongoDB + Files)
echo ============================================

REM Timestamp yyyymmdd-hhmmss
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value ^| find "="') do set dt=%%I
set "TS=%dt:~0,8%-%dt:~8,6%"

set "OUT=backup_%TS%"
if not exist "backups" mkdir backups

echo [i] Membuat MongoDB dump di backups\%OUT%_mongo ...
docker compose exec -T mongo mongodump --archive --gzip --db la_tracker > "backups\%OUT%_mongo.archive.gz"
if errorlevel 1 (
    echo [X] Dump gagal. Pastikan container mongo sedang jalan (start.bat).
    pause
    exit /b 1
)

echo [i] Menyalin attachments ...
if exist "data\attachments" (
    xcopy /E /I /Q /Y "data\attachments" "backups\%OUT%_attachments\" >nul
)

echo.
echo [OK] Backup selesai:
echo      backups\%OUT%_mongo.archive.gz
echo      backups\%OUT%_attachments\
echo.
pause
endlocal
