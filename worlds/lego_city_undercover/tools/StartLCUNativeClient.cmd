@echo off
setlocal
cd /d "%~dp0..\..\.."
start "" ".venv\Scripts\pythonw.exe" "worlds\lego_city_undercover\tools\native_client_gui.py" --name Luma %*
