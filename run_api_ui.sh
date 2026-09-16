#!/usr/bin/env bash
# Run API+UI combined tests only. Extra args are passed to pytest.
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python -m pytest -m api_ui "$@"
