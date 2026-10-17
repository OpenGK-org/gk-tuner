@echo off
cd /d "%~dp0"
python -m gktuner
if errorlevel 1 pause
