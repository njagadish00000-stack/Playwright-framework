#!/usr/bin/env bash
# Run the regression subset. Extra args are passed to pytest.
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python -m pytest -m regression "$@"
