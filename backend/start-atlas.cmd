@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH="
.venv\Scripts\python.exe --version >nul 2>&1
if not errorlevel 1 (
  .venv\Scripts\python.exe -m database.start_atlas
  exit /b
)
set "ASSUREX_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%ASSUREX_PYTHON%" (
  echo Install Python 3.12 and recreate .venv. See installation.txt.
  exit /b 1
)
set "PYTHONPATH=%CD%\.venv\Lib\site-packages"
"%ASSUREX_PYTHON%" -m database.start_atlas
exit /b %errorlevel%
