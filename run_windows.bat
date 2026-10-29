@echo off
title Mini SQL Compiler - SQLite
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  start "" http://127.0.0.1:8000
  py -3 app.py
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    start "" http://127.0.0.1:8000
    python app.py
  ) else (
    echo Python 3 was not found. Install Python 3 and tick Add Python to PATH.
    pause
  )
)
pause
