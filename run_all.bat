@echo off
REM Run the complete test suite (all categories). Extra args are passed to pytest.
cd /d "%~dp0"
.venv\Scripts\python -m pytest %*
