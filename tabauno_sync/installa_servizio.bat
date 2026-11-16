@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
  echo Avvia questo file con il tasto destro, poi "Esegui come amministratore".
  pause
  exit /b 1
)

if not exist "%~dp0config.json" (
  copy /Y "%~dp0config.example.json" "%~dp0config.json" >nul
  echo Creato config.json.
  echo Apri quel file, scrivi i percorsi dei database e il token, poi rilancia questo installer.
  notepad "%~dp0config.json"
  pause
  exit /b 1
)

set "PYTHON="
where py >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)"') do set "PYTHON=%%P"
)
if not defined PYTHON (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3 non trovato. Installalo da https://www.python.org/downloads/ e spunta "Add python.exe to PATH".
    pause
    exit /b 1
  )
  for /f "delims=" %%P in ('where python') do set "PYTHON=%%P" & goto :gotpy
)
:gotpy

set "NSSM=%~dp0nssm.exe"
if not exist "%NSSM%" (
  where nssm >nul 2>&1
  if errorlevel 1 (
    echo Manca nssm.exe in questa cartella.
    echo Scaricalo da https://nssm.cc/download e copia nssm.exe qui, poi rilancia.
    pause
    exit /b 1
  )
  for /f "delims=" %%N in ('where nssm') do set "NSSM=%%N" & goto :gotnssm
)
:gotnssm

"%PYTHON%" -c "import json,sys; c=json.load(open(r'%~dp0config.json',encoding='utf-8')); missing=[k for k in ('tabauno_db','storico_db','mytab_url','agent_token') if not str(c.get(k) or '').strip()]; sys.exit(0 if not missing else 1)"
if errorlevel 1 (
  echo config.json e' incompleto. Servono tabauno_db, storico_db, mytab_url e agent_token.
  notepad "%~dp0config.json"
  pause
  exit /b 1
)

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"
set "CONFIG=%~dp0config.json"

"%NSSM%" stop TabaUnoAgent >nul 2>&1
"%NSSM%" remove TabaUnoAgent confirm >nul 2>&1
"%NSSM%" install TabaUnoAgent "%PYTHON%"
"%NSSM%" set TabaUnoAgent AppDirectory "%ROOT%"
"%NSSM%" set TabaUnoAgent AppParameters "-m tabauno_sync --agent --config \"%CONFIG%\""
"%NSSM%" set TabaUnoAgent AppStdout "%ROOT%\logs\nssm-stdout.log"
"%NSSM%" set TabaUnoAgent AppStderr "%ROOT%\logs\nssm-stderr.log"
"%NSSM%" set TabaUnoAgent AppRotateFiles 1
"%NSSM%" set TabaUnoAgent AppRotateBytes 1048576
"%NSSM%" set TabaUnoAgent Start SERVICE_AUTO_START
"%NSSM%" set TabaUnoAgent AppExit Default Restart
"%NSSM%" set TabaUnoAgent AppRestartDelay 5000
"%NSSM%" set TabaUnoAgent DisplayName "TabaUno Agent myTaba"
"%NSSM%" set TabaUnoAgent Description "Legge la chiusura TabaUno solo quando myTaba lo chiede."
"%NSSM%" start TabaUnoAgent
if errorlevel 1 (
  echo Il servizio non e' partito. Controlla %ROOT%\logs\nssm-stderr.log
  pause
  exit /b 1
)

echo.
echo Servizio TabaUnoAgent avviato. Si riavvia da solo con Windows.
echo Log: %ROOT%\logs\tabauno_agent.log
echo Nel portale, accanto a Importa da TabaUno, deve comparire "PC negozio online".
pause
