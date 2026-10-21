@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed or not on PATH.
  echo Install Python 3.10+ from https://www.python.org/downloads/
  pause
  exit /b 1
)
python -m pip install -r requirements.txt
python app.py
pause
