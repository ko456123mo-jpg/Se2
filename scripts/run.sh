#!/usr/bin/env bash
# Launch the StegoNexus GUI.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 main.py "$@"
