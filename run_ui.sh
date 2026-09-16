#!/usr/bin/env bash
# Run UI tests only. Extra args are passed to pytest.
# Example: ./run_ui.sh --browser webkit --headed
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python -m pytest -m ui "$@"
