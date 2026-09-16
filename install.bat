@echo off
REM Install the Unified Automation Framework (Windows CMD).
setlocal
cd /d "%~dp0"

echo ==^> Checking Python...
python --version || (echo ERROR: Python 3.10+ is required. & exit /b 1)

echo ==^> Creating virtual environment (.venv)...
python -m venv .venv || (echo ERROR: venv creation failed. & exit /b 1)

echo ==^> Installing dependencies...
.venv\Scripts\pip install -U pip || exit /b 1
.venv\Scripts\pip install -r requirements.txt || exit /b 1

echo ==^> Installing Playwright browsers...
.venv\Scripts\python -m playwright install chromium firefox webkit
if errorlevel 1 (
  echo WARNING: browser install failed. API tests still work; retry later with:
  echo   .venv\Scripts\python -m playwright install chromium firefox webkit
)

echo ==^> Validating installation...
.venv\Scripts\python -m pytest --collect-only -q api_tests ui_tests api_ui_tests e2e_tests || exit /b 1

echo.
echo Installation complete. Next steps:
echo   1. copy .env.example .env   ^(optional; defaults already work^)
echo   2. .venv\Scripts\python -m pytest -m smoke
echo   3. .venv\Scripts\python -m server.app   ^(dashboard at http://127.0.0.1:5000^)
