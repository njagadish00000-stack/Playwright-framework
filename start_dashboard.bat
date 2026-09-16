@echo off
REM Start the web dashboard (default http://127.0.0.1:5000).
cd /d "%~dp0"
.venv\Scripts\python -m server.app %*
