@echo off
REM Run end-to-end tests only. Extra args are passed to pytest.
cd /d "%~dp0"
.venv\Scripts\python -m pytest -m e2e %*
