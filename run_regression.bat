@echo off
REM Run the regression subset. Extra args are passed to pytest.
cd /d "%~dp0"
.venv\Scripts\python -m pytest -m regression %*
