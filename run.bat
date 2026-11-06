@echo off
title Cyberpunk 2077 Mod Manager
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo [!] Error running Cyberpunk Mod Manager.
    pause
)
