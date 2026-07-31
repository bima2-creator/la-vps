@echo off
title LA Tracker - Stop
cd /d "%~dp0"

echo ============================================
echo   Menghentikan LA Tracker ...
echo ============================================
docker compose down
echo.
echo [i] Semua service sudah dihentikan.
echo     Data tetap aman di folder .\data\
echo.
pause
