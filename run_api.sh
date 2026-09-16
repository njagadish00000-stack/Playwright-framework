#!/usr/bin/env bash
# Run API tests only. Extra args are passed to pytest.
# Example: ./run_api.sh -n auto
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python -m pytest -m api "$@"
