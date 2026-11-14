@echo off
setlocal
cd /d "%~dp0..\..\.."
set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [LCU] Python-Umgebung fehlt: %CD%\%PYTHON%
  echo [LCU] Bitte zuerst die Archipelago-Venv einrichten.
  pause
  exit /b 1
)
if not exist "worlds\lego_city_undercover\tools\native_client_gui.py" (
  echo [LCU] Die GUI-Datei fehlt im Repository.
  pause
  exit /b 1
)
set "SKIP_REQUIREMENTS_UPDATE=1"
"%PYTHON%" -u "worlds\lego_city_undercover\tools\native_client_gui.py" --name Luma %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
  echo.
  echo [LCU] Der Client wurde mit Fehlercode %RESULT% beendet.
  echo [LCU] Die Fehlermeldung steht oberhalb.
  pause
)
exit /b %RESULT%
