#!/usr/bin/env bash
# Run the smoke subset (fast, critical). Extra args are passed to pytest.
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python -m pytest -m smoke "$@"
