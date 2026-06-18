@echo off
title RapidTech GST Reconciliation - Starting...
color 0A

echo.
echo  ================================================
echo   RapidTech GST Reconciliation App - Launcher
echo  ================================================
echo.

:: ── Step 1: Start Docker Desktop if not running ──────────────────────────────
echo [1/4] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo       Docker not running. Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo       Waiting for Docker to start (this may take 30-60 seconds)...
    :wait_docker
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    if %errorlevel% neq 0 goto wait_docker
    echo       Docker Desktop is ready.
) else (
    echo       Docker Desktop is already running.
)

:: ── Step 2: Navigate to app folder ───────────────────────────────────────────
echo.
echo [2/4] Navigating to app folder...
cd /d "%~dp0"
echo       Folder: %~dp0

:: ── Step 3: Start the app containers ─────────────────────────────────────────
echo.
echo [3/4] Starting app containers...
docker-compose up -d --build 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Failed to start containers. Check Docker Desktop.
    pause
    exit /b 1
)
echo       Containers started successfully.

:: ── Step 4: Wait for backend to be ready ─────────────────────────────────────
echo.
echo [4/4] Waiting for app to be ready...
:wait_app
timeout /t 3 /nobreak >nul
curl -s http://localhost:8000/api/sessions >nul 2>&1
if %errorlevel% neq 0 goto wait_app
echo       App is ready!

:: ── Open Chrome ──────────────────────────────────────────────────────────────
echo.
echo  Opening app in Chrome...
start "" "chrome.exe" http://localhost:3000
if %errorlevel% neq 0 (
    :: Fallback: try default browser
    start http://localhost:3000
)

echo.
echo  ================================================
echo   App is running at: http://localhost:3000
echo   To stop the app, run: stop-app.bat
echo  ================================================
echo.
echo  You can close this window. The app will keep running in the background.
echo.
pause
