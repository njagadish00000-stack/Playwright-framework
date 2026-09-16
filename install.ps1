# Install the Unified Automation Framework (Windows PowerShell).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Checking Python..."
python --version

Write-Host "==> Creating virtual environment (.venv)..."
python -m venv .venv

Write-Host "==> Installing dependencies..."
.venv\Scripts\pip install -U pip
.venv\Scripts\pip install -r requirements.txt

Write-Host "==> Installing Playwright browsers..."
try {
  .venv\Scripts\python -m playwright install chromium firefox webkit
} catch {
  Write-Warning "Browser install failed (offline?). API tests still work; retry later with: .venv\Scripts\python -m playwright install chromium firefox webkit"
}

Write-Host "==> Validating installation..."
.venv\Scripts\python -m pytest --collect-only -q api_tests ui_tests api_ui_tests e2e_tests
.venv\Scripts\python -c "import flask, playwright, pytest, allure_pytest; print('imports OK')"

Write-Host ""
Write-Host "Installation complete. Next steps:"
Write-Host "  1. Copy-Item .env.example .env   (optional; defaults already work)"
Write-Host "  2. .venv\Scripts\python -m pytest -m smoke"
Write-Host "  3. .venv\Scripts\python -m server.app   (dashboard at http://127.0.0.1:5000)"
