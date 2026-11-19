@echo off
cd /d "%~dp0"
title Switch to API Mode
echo.
echo Switching to API mode (real LLM, calls are billed) ...
"%~dp0.venv\Scripts\python.exe" "%~dp0switch_mode.py" api
echo.
pause
