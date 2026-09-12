#!/usr/bin/env bash
# Run the full service preflight check. Uses the project virtualenv when present.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -x ".venv/bin/python" ]; then
    exec ".venv/bin/python" scripts/preflight_check.py "$@"
fi
exec python3 scripts/preflight_check.py "$@"
