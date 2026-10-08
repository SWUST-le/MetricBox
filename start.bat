@echo off
setlocal
cd /d "%~dp0"
title MetricBox
where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.10+ with Tkinter, or run from an Anaconda Prompt.
    pause
    exit /b 1
)
python main.py
if errorlevel 1 pause

