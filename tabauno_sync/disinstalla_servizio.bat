@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
  echo Avvia questo file con il tasto destro, poi "Esegui come amministratore".
  pause
  exit /b 1
)

set "NSSM=%~dp0nssm.exe"
if not exist "%NSSM%" (
  where nssm >nul 2>&1
  if errorlevel 1 (
    echo nssm.exe non trovato.
    pause
    exit /b 1
  )
  for /f "delims=" %%N in ('where nssm') do set "NSSM=%%N" & goto :gotnssm
)
:gotnssm

"%NSSM%" stop TabaUnoAgent
"%NSSM%" remove TabaUnoAgent confirm
echo Servizio rimosso. I database di TabaUno non sono stati toccati.
pause
