@echo off
title SOS Data Bridge
echo Starting SOS System DATA Bridge...

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo "Python is not installed or not in PATH. Please install Python."
    pause
    exit /b
)

REM Check if virtual environment exists, if not create it
if not exist venv (
    echo Creating Python virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo "Failed to create virtual environment."
        pause
        exit /b
    )
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing/updating dependencies from requirements.txt...
pip install -r requirements.txt

echo.
echo Running SOS-System-DATA-Bridge\tv_data_bridge.py...
echo Press Ctrl+C to stop the bridge.
python tv_data_bridge.py

echo.
echo Data bridge has stopped.
pause
