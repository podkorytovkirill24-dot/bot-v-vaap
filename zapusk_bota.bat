@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"

echo Proveryayu zavisimosti...
%PYTHON_EXE% -c "import telegram, telethon" >nul 2>&1
if not "%ERRORLEVEL%"=="0" (
    echo Ustanavlivayu zavisimosti...
    %PYTHON_EXE% -m pip install -r requirements.txt
)

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0zapusk_bota.ps1" -PythonExe "%PYTHON_EXE%"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Zapusk zavershilsya s kodom %EXIT_CODE%.
    echo Log: miniapp_tunnel_err.log
    pause
)

exit /b %EXIT_CODE%
