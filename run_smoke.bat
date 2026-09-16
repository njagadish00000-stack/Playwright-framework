@echo off
REM Run the smoke subset (fast, critical). Extra args are passed to pytest.
cd /d "%~dp0"
.venv\Scripts\python -m pytest -m smoke %*
