#!/usr/bin/env bash
# StegoNexus installer for Kali/Debian. Installs the binary toolchain and Python deps.
# Optional tools (zsteg, wireshark, audacity, rar, pyinstaller) are best-effort: if a
# package cannot be installed StegoNexus will still run and report it as UNAVAILABLE.
set -euo pipefail

cd "$(dirname "$0")/.."
echo "== StegoNexus installer (Kali/Debian) =="

SUDO=""
if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

echo "== [1/3] Binary toolchain (core forensic tools) + Qt GUI runtime libs =="
$SUDO apt-get update -y
$SUDO apt-get install -y --no-install-recommends \
    libimage-exiftool-perl steghide binwalk foremost ffmpeg tshark \
    file binutils p7zip-full \
    libxkbcommon0 libxkbcommon-x11-0 libegl1 libgl1 libglib2.0-0 \
    libdbus-1-3 libfontconfig1 libfreetype6

echo "== [2/3] Optional tools (best effort - failures are OK, reported as UNAVAILABLE) =="
$SUDO apt-get install -y --no-install-recommends wireshark audacity rar || true
# zsteg is a Ruby gem (no Debian package); best effort only.
$SUDO apt-get install -y --no-install-recommends ruby && $SUDO gem install zsteg || true

echo "== [3/3] Python dependencies =="
python3 -m pip install --user -r requirements.txt || python3 -m pip install -r requirements.txt

echo
python3 scripts/check_dependencies.py || true

echo
echo "Install complete. Launch with:  ./scripts/run.sh   (GUI)"
echo "                    or        python3 main.py --cli"
