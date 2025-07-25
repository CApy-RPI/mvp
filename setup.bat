@echo off
setlocal enabledelayedexpansion

echo Setting up development environment...

REM Create virtual environment
echo Creating virtual environment...
python -m venv .venv
if !errorlevel! neq 0 (
    echo Failed to create virtual environment
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if !errorlevel! neq 0 (
    echo Failed to activate virtual environment
    exit /b 1
)

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
if !errorlevel! neq 0 (
    echo Failed to upgrade pip
    exit /b 1
)

REM Install development requirements
echo Installing development requirements...
pip install -r requirements_dev.txt
if !errorlevel! neq 0 (
    echo Failed to install requirements
    exit /b 1
)

REM Install pre-commit hooks
echo Installing pre-commit hooks...
pre-commit install
if !errorlevel! neq 0 (
    echo Failed to install pre-commit hooks
    exit /b 1
)

pre-commit install --hook-type pre-push
if !errorlevel! neq 0 (
    echo Failed to install pre-push hooks
    exit /b 1
)

echo Setup complete!
echo To activate the virtual environment, run: .venv\Scripts\activate.bat
echo To run pre-commit on all files: pre-commit run --all-files

pause
