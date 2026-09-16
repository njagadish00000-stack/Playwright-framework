#!/usr/bin/env bash
# Run end-to-end tests only. Extra args are passed to pytest.
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python -m pytest -m e2e "$@"
