#!/usr/bin/env bash
# Course-practical FFV1 video-hiding workflow (reference).
#
# This mirrors the "practical" FFV1 frame technique using FFmpeg's lossless FFV1 codec so
# that raw frames survive a round trip. It is shipped as a REFERENCE script; the native
# engine lives in app/steganography/video_lsb.py and is what the GUI/tests use.
#
#   encode: scripts/videohide.sh encode <video> <payload> <key> <out.mkv>
#   decode: scripts/videohide.sh decode <stego.mkv> <key> <out.bin>
set -euo pipefail

mode="${1:?encode|decode}"
shift

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

case "$mode" in
  encode)
    video="${1:?video}"; payload="${2:?payload}"; key="${3:?key}"; out="${4:?out.mkv}"
    ffmpeg -v error -y -i "$video" "$work/frame_%08d.png"
    python3 - "$work" "$payload" "$key" <<'PY'
import base64, hashlib, sys
from pathlib import Path
work, payload, key = sys.argv[1:4]
blob = Path(payload).read_bytes()
digest = hashlib.sha256((key + ":" ).encode() + blob).hexdigest()
frames = sorted(Path(work).glob("frame_*.png"))
# Embed one byte per frame by tweaking the least-significant bit of the first pixel
# column - a demonstration only; the production engine is in Python.
from PIL import Image
for i, byte in enumerate(blob):
    if i >= len(frames): break
    img = Image.open(frames[i]).convert("RGB")
    px = img.load()
    w, h = img.size
    for bit in range(8):
        x = bit + 1
        r, g, b = px[x, 0]
        g = (g & ~1) | ((byte >> bit) & 1)
        px[x, 0] = (r, g, b)
    img.save(frames[i])
Path(work, "meta.txt").write_text(f"bytes={len(blob)} sha256={digest}\n")
PY
    ffmpeg -v error -y -framerate 10 -i "$work/frame_%08d.png" -c:v ffv1 "$out"
    echo "encoded -> $out"
    ;;
  decode)
    stego="${1:?stego}"; key="${2:?key}"; out="${3:?out.bin}"
    ffmpeg -v error -y -i "$stego" "$work/frame_%08d.png"
    echo "Reference decode is illustrative; use the Python engine:"
    echo "  python -m app.steganography.video_lsb  (or the GUI Video view)"
    ;;
  *) echo "usage: $0 encode|decode ..." >&2; exit 2 ;;
esac
