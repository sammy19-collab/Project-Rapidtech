@echo off
title RapidTech GST Reconciliation - Starting...
color 0A

echo.
echo  ================================================
echo   RapidTech GST Reconciliation App - Launcher
echo  ================================================
echo.

cd /d "%~dp0"

:: ── Step 1: Check Docker ──────────────────────────────────────────────────────
echo [1/4] Checking Docker Desktop...
docker info >nul 2>&1
if errorlevel 1 goto start_docker
echo       Docker Desktop is already running.
goto docker_ready

:start_docker
echo       Docker not running. Starting Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo       Waiting for Docker to start (this may take 30-60 seconds)...

:wait_docker
timeout /t 5 /nobreak >nul
docker info >nul 2>&1
if errorlevel 1 goto wait_docker
echo       Docker Desktop is ready.

:docker_ready

:: ── Step 2: Start containers ──────────────────────────────────────────────────
echo.
echo [2/4] Starting app containers...
docker-compose up -d --build
if errorlevel 1 (
    echo.
    echo  [ERROR] Failed to start containers. Check Docker Desktop.
    pause
    exit /b 1
)
echo       Containers started successfully.

:: ── Step 3: Wait for backend ──────────────────────────────────────────────────
echo.
echo [3/4] Waiting for app to be ready...

:wait_app
timeout /t 3 /nobreak >nul
curl -s http://localhost:8000/api/sessions >nul 2>&1
if errorlevel 1 goto wait_app
echo       App is ready!

:: ── Step 4: Open browser ──────────────────────────────────────────────────────
echo.
echo [4/4] Opening app in browser...
start http://localhost:3000

echo.
echo  ================================================
echo   App is running at: http://localhost:3000
echo   To stop the app, run: stop-app.bat
echo  ================================================
echo.
echo  You can close this window. The app keeps running in the background.
echo.
pause
