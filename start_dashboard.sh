#!/usr/bin/env bash
# Start the web dashboard (default http://127.0.0.1:5000).
# Example: ./start_dashboard.sh --port 5001
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python -m server.app "$@"
