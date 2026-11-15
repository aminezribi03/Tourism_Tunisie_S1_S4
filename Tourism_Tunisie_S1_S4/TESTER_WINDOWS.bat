@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Lancez d'abord INSTALLER_WINDOWS.bat.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 goto failed
echo Tests termines avec succes.
pause
exit /b 0
:failed
echo Un controle a echoue. Lisez le message ci-dessus.
pause
exit /b 1
