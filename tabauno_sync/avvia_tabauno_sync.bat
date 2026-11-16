@echo off
REM Prova manuale. Per l'avvio automatico usa INSTALL_WINDOWS.md (NSSM).
cd /d "%~dp0\.."
python -m tabauno_sync --agent --config "%~dp0config.json"
if errorlevel 1 pause
