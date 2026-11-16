@echo off
cd /d "%~dp0\.."
python -m tabauno_sync --service --config "%~dp0config.json"
if errorlevel 1 pause
