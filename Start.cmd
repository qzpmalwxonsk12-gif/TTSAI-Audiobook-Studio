@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup-cloud.cmd first for cloud APIs, or Setup.cmd for the original local models.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" start.py
pause
