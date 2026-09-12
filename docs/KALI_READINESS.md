# StegoNexus — Kali Readiness

Verified on a clean Linux sandbox by running **every technique for real**
(`scripts/preflight_check.py`, true round-trips compared byte-for-byte).
Result: **READY — 0 FAIL**.

## Install on Kali (one command)

```bash
sudo ./scripts/install_kali.sh     # forensic tools + Qt GUI libs + Python deps + zsteg
python scripts/preflight_check.py  # prints PASS/FAIL for every service
./scripts/run.sh                   # launch the GUI
```

`install_kali.sh` installs: exiftool, steghide, binwalk, foremost, ffmpeg/ffprobe,
tshark, file, binutils, p7zip, the Qt runtime libs (libxkbcommon0/libegl1/libgl1/…),
then `pip install -r requirements.txt` (PySide6, numpy, Pillow, cryptography, scapy),
and best-effort `gem install zsteg`.

## Preflight result (22 checks)

| Service | Status | Evidence |
| --- | --- | --- |
| Tools installed (9) | PASS | exiftool/ffmpeg/ffprobe/steghide/binwalk/foremost/tshark/file/strings |
| Python deps | PASS | PySide6/cryptography/scapy/PIL/numpy |
| Case + evidence + 4-algo hashing | PASS | verify_match=True |
| Metadata read/inject/strip | PASS | original unchanged |
| Text LSB round-trip | PASS | recovered match |
| Image native LSB | PASS | byte_match |
| Image Steghide (JPEG) | PASS | byte_match |
| Audio LSB | PASS | byte_match |
| Audio phase coding | PASS | byte_match (16 s carrier) |
| **Audio spread-spectrum (DSSS)** | **PASS** | **blind extract byte_match (native engine, 30 s carrier)** |
| Video LSB (lossless .mkv) | PASS | byte_match |
| Video EOF container | PASS | detected + byte_match (not OpenPuff) |
| Network encode preview | PASS | IPv4-ID field map |
| Network capture analysis | PASS | 17 packets, confidence=High |
| **Network send/receive (UDP loopback)** | **PASS** | **real round-trip, no root** |
| Malware static analysis | PASS | score/indicators, never executed |
| Forensics suite (8 tools) | PASS | file/strings/entropy/binwalk/steghide/ffprobe/foremost/triage |
| Reports PDF/HTML/JSON | PASS | 3 files |
| GUI (all 20 views) | PASS | smoke 20/20 |
| Network IPv4-ID covert channel | GATED | needs root (raw sockets) → works on Kali via `sudo` |
| zsteg | UNAVAILABLE here | installed on Kali by `install_kali.sh` |
| Malware dynamic / sandbox | BLOCKED | by safety design — samples never executed |

**Summary: 19 PASS · 1 GATED · 1 UNAVAILABLE · 1 BLOCKED · 0 FAIL → READY.**

## What this session fixed (real code, not docs)

- **Audio spread-spectrum is now a real implementation.** Added
  `app/steganography/audio_spread.py` — a native Direct-Sequence Spread-Spectrum
  codec for 16-bit PCM WAV (key-derived PN chips, blind *and* differential
  detection). The audio service now uses it instead of the video-frame engine, so
  spread-spectrum on audio is **IMPLEMENTED / PASS** (was PARTIAL). Wrong key
  correctly fails; CRC + length are verified.
- **Network send/receive proven for real.** The preflight enables *Authorized
  laboratory mode*, runs a receiver thread and a sender on loopback, and confirms
  the payload round-trips over the baseline UDP channel — **without root**. The
  covert IPv4-ID channel additionally needs raw sockets, so it is GATED until you
  run with `sudo` (loopback / RFC1918 only, by policy).
- **`install_kali.sh` hardened** with the Qt GUI runtime libraries so the GUI runs
  on a minimal Kali install.

## Using every service on Kali

- **All implemented services work** after `install_kali.sh`.
- **Network covert IPv4-ID channel:** run the GUI/sender with `sudo` and enable
  *Authorized laboratory mode* in Settings; restricted to loopback / RFC1918.
- **zsteg:** available once `install_kali.sh` installs the Ruby gem.

## Honest limitations (unchanged, by design)

- **Malware dynamic analysis / sandbox detonation:** always BLOCKED — StegoNexus
  is defensive and never executes specimens (static analysis + simulation only).
- **Windows-only tools** (OpenPuff, DeepSound, Coagula) and **CyberHide** remain
  REFERENCE/EXTERNAL: no native Linux binaries; run them yourself (Wine) if needed.
- **Steghide + PNG:** unsupported by Steghide itself — use JPEG/BMP/AU/WAV.
- **Audio spread-spectrum** needs a carrier long enough for the payload (it is a
  low-bitrate channel); the preflight uses a 30 s carrier.

Re-run the check any time with:

```bash
python scripts/preflight_check.py     # writes artifacts/preflight/preflight_result.json
```
