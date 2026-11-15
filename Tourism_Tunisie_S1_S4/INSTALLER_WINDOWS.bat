@echo off
setlocal
cd /d "%~dp0"
echo Installation du projet Tourisme Tunisie
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3.12 -c "import sys" >nul 2>nul
if errorlevel 1 goto use_python
py -3.12 -m venv .venv
goto install
:use_python
where python >nul 2>nul
if errorlevel 1 goto no_python
python -c "import sys; assert sys.version_info[:2] == (3,12)" >nul 2>nul
if errorlevel 1 goto no_python
python -m venv .venv
:install
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m tourism.etl
if errorlevel 1 goto failed
".venv\Scripts\python.exe" scripts\configure_powerbi.py
if errorlevel 1 goto failed
echo.
echo Installation terminee. Ouvrez LANCER_WINDOWS.bat.
pause
exit /b 0
:no_python
echo Installez Python 3.12 64 bits depuis https://www.python.org/downloads/
echo Cochez Add Python to PATH, puis relancez ce fichier.
pause
exit /b 1
:failed
echo.
echo Echec. Lisez le message ci-dessus. Verifiez Python 3.12 et la connexion Internet.
pause
exit /b 1
