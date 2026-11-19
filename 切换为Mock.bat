@echo off
cd /d "%~dp0"
title Switch to Mock Mode
echo.
echo Switching to MOCK mode (no real API calls, no cost) ...
"%~dp0.venv\Scripts\python.exe" "%~dp0switch_mode.py" mock
echo.
pause
