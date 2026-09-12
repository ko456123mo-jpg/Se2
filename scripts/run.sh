#!/usr/bin/env bash
# Launch the StegoNexus GUI. Uses the project virtualenv when present.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -x ".venv/bin/python" ]; then
    exec ".venv/bin/python" main.py "$@"
fi
exec python3 main.py "$@"
