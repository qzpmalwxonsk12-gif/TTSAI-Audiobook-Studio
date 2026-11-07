@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements-cloud.txt
if errorlevel 1 exit /b 1
echo Cloud setup complete. Run Start.cmd, then add free API keys in Cloud connections.
pause
