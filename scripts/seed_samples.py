#!/usr/bin/env python3
"""Generate the benign synthetic sample set used by the demo, tests and slides.

Everything here is synthetic and harmless:
  text    - a neutral paragraph + a short secret
  images  - a random-noise carrier (PNG) and a JPEG photo-like gradient
  audio   - a 16-bit sine/white-noise WAV written with the stdlib wave module
  video   - an MP4 produced by ffmpeg's lavfi testsrc (skipped if ffmpeg absent)
  network - loopback-safe .pcap captures synthesized with scapy (no traffic sent)
  malware - benign fixtures only (a text file and a zip); never a real specimen

Nothing is downloaded and nothing is executed.
"""
from __future__ import annotations

import struct
import sys
import wave
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from app.core.config import get_config  # noqa: E402

_PARA = (
    "The lighthouse keeper recorded the tide at dawn and noted that the gulls "
    "returned to the eastern rocks before the rain arrived. The harbour master "
    "confirmed two vessels departed after midnight, each flying a blue pennant. "
    "By noon the fog had lifted and the channel markers were repainted white."
)
# Repeated so the cover always carries ample LSB capacity for the test payloads.
COVER_TEXT = " ".join([_PARA] * 4)


def seed() -> dict:
    cfg = get_config()
    base = cfg.samples_dir
    out: dict[str, Path] = {}
    for sub in ("text", "images", "audio", "video", "network", "malware"):
        (base / sub).mkdir(parents=True, exist_ok=True)

    # text ---------------------------------------------------------------------
    cover = base / "text" / "cover.txt"
    cover.write_text(COVER_TEXT + "\n")
    secret = base / "text" / "secret.txt"
    secret.write_text("StegoNexus sample payload 0123456789.\n")
    out["text_cover"] = cover
    out["text_secret"] = secret

    # images -------------------------------------------------------------------
    rng = np.random.default_rng(7)
    noise = rng.integers(0, 256, (256, 256, 3), dtype=np.uint8)
    png = base / "images" / "carrier_noise.png"
    Image.fromarray(noise, "RGB").save(png)
    yy, xx = np.mgrid[0:256, 0:256]
    gradient = np.stack([xx % 256, yy % 256, (xx + yy) % 256], axis=-1).astype(np.uint8)
    jpg = base / "images" / "carrier_gradient.jpg"
    Image.fromarray(gradient, "RGB").save(jpg, quality=92)
    out["image_png"] = png
    out["image_jpg"] = jpg

    # audio --------------------------------------------------------------------
    sr = 8000
    seconds = 2
    t = np.linspace(0, seconds, sr * seconds, endpoint=False)
    tone = 0.35 * np.sin(2 * np.pi * 440 * t) + 0.05 * rng.standard_normal(t.shape)
    pcm = np.int16(np.clip(tone, -1, 1) * 32767)
    wav = base / "audio" / "carrier.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    out["audio_wav"] = wav

    # video (optional - needs ffmpeg) ------------------------------------------
    from app.services.tool_executor import executor

    if executor.is_available("ffmpeg"):
        mp4 = base / "video" / "carrier.mp4"
        executor.run("ffmpeg", ["-y", "-v", "error", "-f", "lavfi",
                                "-i", "testsrc=size=96x96:rate=10:duration=2",
                                "-pix_fmt", "yuv420p", str(mp4)], timeout=120)
        if mp4.exists():
            out["video_mp4"] = mp4

    # network (offline synthesis - no packets are transmitted) -----------------
    try:
        from scapy.all import IP, UDP, wrpcap  # noqa: PLC0415

        from app.network import encoder  # noqa: PLC0415

        encoded = encoder.encode(b"SNX-LAB-PCAP")
        covert = []
        for ip_id in encoded.ip_ids:
            covert.append(IP(dst="127.0.0.1", id=ip_id) / UDP(sport=53000, dport=53000))
        wrpcap(str(base / "network" / "covert_lab.pcap"), covert)
        out["net_covert"] = base / "network" / "covert_lab.pcap"

        benign = [IP(dst="127.0.0.1", id=i) / UDP(sport=40000, dport=40000)
                  for i in range(1, 41)]
        wrpcap(str(base / "network" / "benign_lab.pcap"), benign)
        out["net_benign"] = base / "network" / "benign_lab.pcap"
    except Exception as exc:  # noqa: BLE001 - network samples are optional
        print(f"  (network samples skipped: {exc})")

    # malware (benign fixtures only) -------------------------------------------
    benign_txt = base / "malware" / "benign_note.txt"
    benign_txt.write_text("This is a benign sample used to exercise the static "
                          "analyser. It contains no executable code.\n")
    zpath = base / "malware" / "benign_archive.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("readme.txt", "benign archive entry\n")
    out["mal_txt"] = benign_txt
    out["mal_zip"] = zpath

    # synthetic PE training carrier (headers + padded section, NO code) --------
    pe_carrier = base / "malware" / "training_carrier.exe"
    pe_carrier.write_bytes(build_synthetic_pe())
    out["pe_carrier"] = pe_carrier
    return out


def build_synthetic_pe() -> bytes:
    """A minimal, parseable PE32+ file used as a stego carrier in the lab.

    It has a DOS header/stub, one ``.text`` section whose raw data is 1024
    bytes while only 256 bytes are virtually used - i.e. 768 bytes of slack
    space - and **no executable code** (entry point 0, no imports).  It exists
    purely to teach executable-carrier steganography; nothing here can or
    should be run.
    """
    dos = bytearray(0x80)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, 0x80)
    stub = b"StegoNexus TRAINING CARRIER - synthetic data, not real code.\r\n$"
    dos[0x40:0x40 + len(stub)] = stub

    pe_sig = b"PE\x00\x00"
    coff = struct.pack("<HHIIIHH", 0x8664, 1, 0x65000000, 0, 0, 240, 0x0022)
    opt = bytearray(240)                           # PE32+ optional header
    struct.pack_into("<H", opt, 0, 0x20B)          # magic PE32+
    struct.pack_into("<I", opt, 4, 0x0400)         # size of code
    struct.pack_into("<I", opt, 16, 0)             # entry point 0 (no code)
    struct.pack_into("<I", opt, 20, 0x1000)        # base of code
    struct.pack_into("<Q", opt, 24, 0x140000000)   # image base
    struct.pack_into("<I", opt, 32, 0x1000)        # section alignment
    struct.pack_into("<I", opt, 36, 0x0200)        # file alignment
    struct.pack_into("<H", opt, 40, 6)             # major OS version
    struct.pack_into("<H", opt, 48, 6)             # major subsystem version
    struct.pack_into("<I", opt, 56, 0x10000)       # size of image
    struct.pack_into("<I", opt, 60, 0x0400)        # size of headers
    struct.pack_into("<H", opt, 68, 3)             # subsystem: console
    struct.pack_into("<H", opt, 70, 0x1600)        # dll characteristics
    struct.pack_into("<Q", opt, 72, 0x100000)      # stack reserve
    struct.pack_into("<Q", opt, 80, 0x1000)        # stack commit
    struct.pack_into("<Q", opt, 88, 0x100000)      # heap reserve
    struct.pack_into("<Q", opt, 96, 0x1000)        # heap commit
    struct.pack_into("<I", opt, 108, 16)           # number of RVA and sizes
    section = struct.pack("<8sIIIIIIHHI", b".text", 256, 0x1000, 1024, 0x400,
                          0, 0, 0, 0, 0x60000020)
    body = b"\x00" * 1024                          # section raw data (padding)
    header = bytes(dos) + pe_sig + coff + bytes(opt) + section
    header += b"\x00" * (0x400 - len(header))      # pad headers to file alignment
    return header + body


def main() -> int:
    result = seed()
    for key, path in result.items():
        print(f"  {key:<12} {path} ({path.stat().st_size} bytes)")
    print(f"Seeded {len(result)} sample file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
