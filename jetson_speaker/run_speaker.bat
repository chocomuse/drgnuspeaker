@echo off
title Drgnu Jetson Speaker
cd /d "%~dp0"
echo ==================================================
echo         Drgnu Jetson Speaker Client
echo ==================================================
echo.

if exist .venv\Scripts\activate.bat (
    echo [INFO] Activating virtual environment venv...
    call .venv\Scripts\activate.bat
) else (
    echo [WARN] Virtual environment venv not found.
    echo        Attempting to run using system Python...
)

echo [INFO] Starting Speaker Client...
python -m drgnu_speaker.main

echo.
echo ==================================================
echo  Speaker Client stopped. Press any key to exit.
echo ==================================================
pause
