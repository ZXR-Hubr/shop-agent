@echo off
cd /d "%~dp0"
title Configure Aliyun Bailian (DashScope) API Key
echo ==============================================
echo   Configure Aliyun Bailian API Key
echo ==============================================
echo.
echo   1) Open https://bailian.console.aliyun.com
echo   2) Activate the "Bailian / Model Studio" service
echo   3) Top right corner: API-KEY -^> create or view
echo   4) Copy the key starting with sk-
echo.

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" goto novenv

"%PY%" setup_key.py
if errorlevel 2 goto end
echo.
echo Running self-check ...
echo.
"%PY%" check_llm.py

:end
echo.
pause
exit /b 0

:novenv
echo [ERROR] .venv not found. Please run start.bat once first.
echo.
pause
exit /b 1
