#!/usr/bin/env bash
# Install the Unified Automation Framework (Linux/macOS).
# Creates .venv, installs dependencies + Playwright browsers, validates setup.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Checking Python..."
python3 --version || { echo "ERROR: python3 is required."; exit 1; }

echo "==> Creating virtual environment (.venv)..."
python3 -m venv .venv

echo "==> Installing dependencies..."
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

echo "==> Installing Playwright browsers (chromium, firefox, webkit)..."
.venv/bin/python -m playwright install chromium firefox webkit || {
  echo "WARNING: browser install failed (offline?). API tests still work; install browsers later with:";
  echo "  .venv/bin/python -m playwright install chromium firefox webkit";
}

echo "==> Installing system dependencies for headless browsers (may need sudo)..."
.venv/bin/python -m playwright install-deps chromium firefox webkit 2>/dev/null || echo "(skipped: install-deps needs root or is unsupported here)"

echo "==> Validating installation..."
.venv/bin/python -m pytest --collect-only -q api_tests ui_tests api_ui_tests e2e_tests | tail -2
.venv/bin/python -c "import flask, playwright, pytest, allure_pytest; print('imports OK')"

echo ""
echo "Installation complete. Next steps:"
echo "  1. cp .env.example .env   (optional; defaults already work)"
echo "  2. .venv/bin/python -m pytest -m smoke"
echo "  3. .venv/bin/python -m server.app   (dashboard at http://127.0.0.1:5000)"
