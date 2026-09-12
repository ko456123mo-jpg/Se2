# AUDIT_BEFORE_REPAIR.md — StegoNexus

Audit performed **before** the repair/completion phase. Every status below was
measured by executing the code or probing the environment on 2026-09-12
(Debian 13 sandbox used as the Kali-equivalent test host; tools listed are the
same packages Kali ships). **No status was assumed.**

Legend of statuses used: `IMPLEMENTED` (native, working), `INTEGRATED` (external
tool wired through ToolExecutor), `PARTIAL`, `MISSING`, `BROKEN`, `SIMULATED`,
`REFERENCE`, `EXTERNAL`, `OPTIONAL`, `UNAVAILABLE`.

## Environment probe (measured)

| Dependency | Status | Version measured | Notes |
|---|---|---|---|
| Python | AVAILABLE | 3.13.14 | |
| PySide6 | AVAILABLE | 6.11.2 | GUI + QtSvg + QtPdf |
| Pillow | AVAILABLE | 12.3.0 | |
| NumPy | AVAILABLE | 2.3.5 | |
| cryptography | AVAILABLE | 50.0.1 | |
| scapy | AVAILABLE | 2.7.0 | |
| exiftool | AVAILABLE | 13.25 | `libimage-exiftool-perl` |
| file | AVAILABLE | 5.46 | |
| strings | AVAILABLE | GNU binutils 2.44 | |
| binwalk | AVAILABLE | 2.4.3 | |
| steghide | AVAILABLE | 0.5.1 | |
| foremost | AVAILABLE | 1.5.7 | |
| zsteg | **UNAVAILABLE** | — | Ruby gem; **no Debian package** — never faked |
| ffmpeg / ffprobe | AVAILABLE | 7.1.5 | |
| tshark | AVAILABLE | 4.4.18 | |
| audacity | UNAVAILABLE | — | EXTERNAL/optional |
| wireshark GUI | UNAVAILABLE | — | tshark present instead |

## Component audit

| Component | Status | Files | Working? | Tests? | Dependencies | Required changes | Priority |
|---|---|---|---|---|---|---|---|
| Core config/security/logging/models | IMPLEMENTED | `app/core/*.py` | Yes | ad-hoc | stdlib | none | — |
| SQLite storage layer | IMPLEMENTED | `app/storage/{database.py,schema.sql}` | Yes | ad-hoc | sqlite3 | none | — |
| ToolExecutor / ToolHealth | IMPLEMENTED | `app/services/*.py` | Yes (14/24 tools on host) | ad-hoc | subprocess | none | — |
| Text LSB+Key | IMPLEMENTED | `app/steganography/{bitstream,lsb_text}.py` | Yes (round-trip, wrong-key, capacity verified) | manual | stdlib | unit tests | P1 |
| Image native LSB | IMPLEMENTED | `app/steganography/lsb_image.py` | Yes (verified round-trip, ref-diff cross-check) | manual | Pillow, numpy | unit tests | P1 |
| Image Steghide | INTEGRATED | `app/modules/image/service.py` | Yes (embed/extract/info verified with real steghide) | manual | steghide | unit tests | P1 |
| Audio LSB | IMPLEMENTED | `app/steganography/lsb_audio.py` | Yes (SNR 102.9 dB, round-trip) | manual | numpy | unit tests | P1 |
| Audio phase coding | IMPLEMENTED (fragile by design) | `app/steganography/phase_coding.py` | Yes (round-trip + noise ≥20 dB; SNR reported) | manual | numpy | unit tests | P1 |
| Audio spread spectrum | IMPLEMENTED | `app/steganography/spread_spectrum.py` | Yes (blind + differential) | manual | numpy | unit tests | P1 |
| Audio metadata / waveform / spectrogram | IMPLEMENTED | `app/modules/audio/service.py` | Yes | manual | exiftool/ffmpeg | UI | P1 |
| Video LSB (FFV1) | IMPLEMENTED | `app/steganography/video_lsb.py` | Yes (round-trip verified via ffmpeg) | manual | ffmpeg | unit tests | P1 |
| Video EOF container | IMPLEMENTED (custom academic) | `app/steganography/container.py` | Yes (AES-GCM, wrong-key detection) | manual | cryptography | unit tests | P1 |
| Video spread spectrum | IMPLEMENTED (educational) | `app/steganography/video_spread.py` | Yes (blind @alpha 16; differential @alpha 4) | manual | ffmpeg | unit tests | P1 |
| Network IPv4-ID / UDP / pcap / interpreter | IMPLEMENTED (lab-gated) | `app/network/*.py`, `app/modules/network/service.py` | Yes (codec verified; loopback live test pending) | manual | scapy | sudo live-lab test | P1 |
| Malware static/IOC/evasion | IMPLEMENTED (defensive) | `app/malware/*.py`, `app/modules/malware/service.py` | Yes | manual | stdlib | unit tests | P1 |
| Forensics (file/strings/exiftool/binwalk/steghide info/foremost/zsteg/entropy) | IMPLEMENTED | `app/modules/forensics/service.py` | Yes; zsteg honestly UNAVAILABLE | manual | tools | UI | P1 |
| Hashing MD5/SHA-1/SHA-256/SHA-512 | IMPLEMENTED | `app/modules/hashing/service.py` | Yes | manual | hashlib | unit tests | P1 |
| Cases/Evidence/Findings/Logs/Extraction/Dashboard/Settings | IMPLEMENTED | `app/modules/*/service.py` | Yes | manual | sqlite | UI | P1 |
| Reports HTML/JSON/PDF | **PARTIAL** | `app/modules/reports/service.py` | HTML/JSON OK; **PDF not yet executed** | **No** | PySide6 QtPdf | verify PDF headless; decouple from GUI | P0 |
| Branding (SVG/PNG) | IMPLEMENTED | `resources/branding/*`, `scripts/render_branding.py` | Yes (rendered, visually verified) | n/a | QtSvg | none | — |
| End-to-end demo script | **PARTIAL** | `scripts/demo_end_to_end.py` | Written, **never executed** | **No** | all | run + fix | P0 |
| **PySide6 GUI** | **MISSING** | `app/gui/` (empty) | No | No | PySide6 | **build entire GUI** | **P0** |
| `main.py` entry point | **MISSING** | — | No | No | PySide6 | create | **P0** |
| `requirements.txt` | **MISSING** | — | — | — | — | create | P0 |
| Kali scripts (install/check/run/uninstall/desktop) | **MISSING** | `scripts/` only has demo+render | No | No | bash | create | P0 |
| Tests suite | **MISSING** | `tests/` empty | No | No | pytest | create full suite | P1 |
| Documentation | **MISSING** | `docs/` empty | No | No | — | create all docs | P2 |
| Presentation | **MISSING** | `presentation/` empty | No | No | python-pptx | build with real screenshots | P2 |
| Traceability / oral guide | **MISSING** | — | No | No | — | create | P2 |

## Summary of gaps driving the repair plan

1. **P0** – no GUI, no `main.py`, no `requirements.txt`, no Kali scripts, PDF report
   unverified, end-to-end demo never executed.
2. **P1** – no automated test suite; all verification so far was manual.
3. **P2** – no documentation, presentation, traceability matrix, oral-defense guide.
4. **P3** – cleanup and final packaging.

Nothing that already works will be rewritten; the repair only adds the missing
layers and the missing verification.
