#!/usr/bin/env bash
# Remove the desktop integration. Runtime data (data/, logs/, cases/, reports/) is left
# untouched unless --purge is passed, because it may contain evidence.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -f "$HOME/.local/share/applications/stegonexus.desktop"
rm -f "$HOME/.local/share/icons/stegonexus.png"
echo "Desktop entry and icon removed."

if [ "${1:-}" = "--purge" ]; then
    read -r -p "This deletes data/, logs/, cases/, reports/ (evidence!). Type DELETE to continue: " CONFIRM
    if [ "$CONFIRM" = "DELETE" ]; then
        rm -rf data logs cases reports
        echo "Runtime data purged."
    else
        echo "Aborted: runtime data preserved."
    fi
else
    echo "Runtime data preserved. Use --purge (with confirmation) to remove it."
fi
