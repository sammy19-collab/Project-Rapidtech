@echo off
title RapidTech GST Reconciliation - Stopping...
color 0C

echo.
echo  ================================================
echo   RapidTech GST Reconciliation App - Stop
echo  ================================================
echo.

cd /d "%~dp0"

echo Stopping app containers...
docker-compose down
echo.
echo  App stopped. Your data is preserved in the database.
echo  Run start-app.bat to start again.
echo.
pause
