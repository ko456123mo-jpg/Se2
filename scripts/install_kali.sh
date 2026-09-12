#!/usr/bin/env bash
# StegoNexus installer for Kali/Debian. Installs the binary toolchain and Python deps.
# Optional tools (zsteg, wireshark, audacity, rar, pyinstaller) are best-effort: if a
# package cannot be installed StegoNexus will still run and report it as UNAVAILABLE.
#
# Python packages go into a project-local virtualenv (.venv). Kali/Debian mark the
# system interpreter as "externally managed" (PEP 668), which makes a plain
# `pip install` fail - the venv avoids that without touching the system Python.
set -euo pipefail

cd "$(dirname "$0")/.."
echo "== StegoNexus installer (Kali/Debian) =="

SUDO=""
if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

echo "== [1/4] Binary toolchain (core forensic tools) + Qt GUI runtime libs =="
$SUDO apt-get update -y
$SUDO apt-get install -y --no-install-recommends \
    libimage-exiftool-perl steghide binwalk foremost ffmpeg tshark \
    file binutils p7zip-full \
    libxkbcommon0 libxkbcommon-x11-0 libegl1 libgl1 libglib2.0-0 \
    libdbus-1-3 libfontconfig1 libfreetype6

echo "== [2/4] Optional tools (best effort - failures are OK, reported as UNAVAILABLE) =="
$SUDO apt-get install -y --no-install-recommends wireshark audacity rar || true
# zsteg is a Ruby gem (no Debian package); best effort only.
$SUDO apt-get install -y --no-install-recommends ruby && $SUDO gem install zsteg || true

echo "== [3/4] Python virtualenv =="
# venv support is split out on Debian/Kali; install it if missing.
$SUDO apt-get install -y --no-install-recommends python3-venv python3-full || true

# PySide6 needs Python >=3.10,<3.15. Pick the first interpreter in that range.
PY=""
for candidate in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$candidate" >/dev/null 2>&1 && \
       "$candidate" -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,15) else 1)' \
       >/dev/null 2>&1; then
        PY="$candidate"; break
    fi
done
if [ -z "$PY" ]; then
    echo "ERROR: no Python in the supported range 3.10-3.14 was found." >&2
    echo "       PySide6 requires >=3.10,<3.15. Install one, e.g.:" >&2
    echo "       sudo apt install python3.13 python3.13-venv" >&2
    exit 1
fi
echo "   using $($PY -V 2>&1)"

echo "== [4/4] Python dependencies (into .venv) =="
if [ ! -x ".venv/bin/python" ]; then
    "$PY" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
if ! .venv/bin/python -m pip install -r requirements.txt; then
    echo "   venv install failed; falling back to a system-wide install" >&2
    python3 -m pip install --break-system-packages -r requirements.txt
fi

echo
if [ -x ".venv/bin/python" ]; then
    .venv/bin/python scripts/check_dependencies.py || true
else
    python3 scripts/check_dependencies.py || true
fi

echo
echo "Install complete."
echo "  Launch GUI ............ ./scripts/run.sh        (auto-uses .venv)"
echo "  Verify every service .. ./scripts/preflight.sh"
echo "  Or activate manually ... source .venv/bin/activate"
