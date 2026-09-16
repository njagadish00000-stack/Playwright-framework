@echo off
REM Run UI tests only. Extra args are passed to pytest.
cd /d "%~dp0"
.venv\Scripts\python -m pytest -m ui %*
