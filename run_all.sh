#!/usr/bin/env bash
# Run the complete test suite (all categories). Extra args are passed to pytest.
# Example: ./run_all.sh --browser firefox --headed -n auto
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python -m pytest "$@"
