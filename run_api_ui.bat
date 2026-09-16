@echo off
REM Run API+UI combined tests only. Extra args are passed to pytest.
cd /d "%~dp0"
.venv\Scripts\python -m pytest -m api_ui %*
