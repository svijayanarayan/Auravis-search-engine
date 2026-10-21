@echo off
cd /d "%~dp0"
if not exist venv\Scripts\python.exe (
  echo Creating AURAVIS virtual environment...
  python -m venv venv
  if errorlevel 1 goto fail
  echo Installing AURAVIS dependencies...
  venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto fail
)
echo Starting AURAVIS...
venv\Scripts\python.exe app.py
pause
goto :eof
:fail
echo.
echo AURAVIS setup failed. Run these commands manually in CMD:
echo python -m venv venv
echo venv\Scripts\activate.bat
echo python -m pip install -r requirements.txt
echo python app.py
pause
