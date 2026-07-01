@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD=python"
where py >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not exist ".venv" (
    echo Creando entorno virtual...
    %PYTHON_CMD% -m venv .venv
)

set "VENV_PY=.venv\Scripts\python.exe"

"%VENV_PY%" -m pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias, puede tardar un poco la primera vez...
    "%VENV_PY%" -m pip install -r requirements.txt
)

"%VENV_PY%" app.py
pause
