@echo off
setlocal
cd /d "%~dp0..\..\.."
set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [LCU] Die Archipelago-Python-Umgebung fehlt.
  pause
  exit /b 1
)
echo [LCU] LEGO City und den AP-Client vor dem Rebuild schliessen!
echo [LCU] Der gezielte Cheat-Quellcodefix wird zuerst geprueft.
echo [LCU] Danach wird die Native-DLL neu gebaut und versioniert.
"%PYTHON%" worlds\lego_city_undercover\tools\rebuild_native_bridge.py
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [LCU] DLL-Build fehlgeschlagen. Falls ziglang fehlt:
  echo   .venv\Scripts\python.exe -m pip install ziglang
)
echo.
pause
exit /b %RC%
