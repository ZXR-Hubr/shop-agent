@echo off
cd /d "%~dp0"
title Xiaoman Shop - LLM Customer Service Agent
echo ==============================================
echo   Xiaoman Shop - LLM Customer Service Agent
echo   Folder: %~dp0
echo   Open  : http://127.0.0.1:8000
echo   Stop  : press Ctrl+C in this window
echo ==============================================
echo.

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 goto portbusy

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" goto novenv

echo Starting server, please wait a few seconds ...
echo (Keep this window open. It IS the server.)
echo.
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
echo.
echo Server stopped.
pause
exit /b 0

:portbusy
echo [NOTICE] Port 8000 is already in use.
echo          Close the previous black window, or run:
echo          netstat -ano ^| findstr :8000
echo          taskkill /PID ^<pid^> /F
echo.
pause
exit /b 1

:novenv
echo [ERROR] .venv not found in this folder.
echo         Run these two commands once:
echo             python -m venv .venv
echo             .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 1
