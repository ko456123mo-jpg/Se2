#!/usr/bin/env bash
# Register StegoNexus as a desktop application (menu entry + launcher icon).
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT="$(pwd)"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons"
mkdir -p "$APPS_DIR" "$ICON_DIR"

cp -f resources/icons/stegonexus-256.png "$ICON_DIR/stegonexus.png"

cat > "$APPS_DIR/stegonexus.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=StegoNexus
GenericName=Steganography Investigation Workstation
Comment=Hide, extract, analyze, verify, investigate, document and report.
Exec=$ROOT/scripts/run.sh
Icon=$ICON_DIR/stegonexus.png
Terminal=false
Categories=Security;Education;Science;
Keywords=steganography;forensics;
EOF

chmod +x "$ROOT/scripts/run.sh"
echo "Desktop entry installed: $APPS_DIR/stegonexus.desktop"
echo "Refresh the menu or run:  xdg-open $APPS_DIR/stegonexus.desktop"
