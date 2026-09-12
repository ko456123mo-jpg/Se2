# Module & Tool Status Matrix

Measured on this build (see **Tool Health** view / `scripts/check_dependencies.py`).

## External tools

| Tool | Status | Classification | Used by |
|------|--------|----------------|---------|
| exiftool 13.25 | AVAILABLE | INTEGRATED | Metadata read/inject/strip/compare |
| file 5.46 | AVAILABLE | INTEGRATED | Forensics file-type |
| strings 2.44 | AVAILABLE | INTEGRATED | Forensics strings |
| binwalk 2.4.3 | AVAILABLE | INTEGRATED | Forensics signatures |
| steghide 0.5.1 | AVAILABLE | INTEGRATED | Image Steghide embed/extract/info |
| foremost 1.5.7 | AVAILABLE | INTEGRATED | Forensics carving |
| ffmpeg / ffprobe 7.1.5 | AVAILABLE | INTEGRATED | Audio/video conversion + probing |
| tshark 4.4.16 | AVAILABLE | INTEGRATED | Network capture parsing |
| zsteg | UNAVAILABLE | UNAVAILABLE | (honest; `sudo gem install zsteg`) |
| wireshark | UNAVAILABLE | EXTERNAL | Open capture in GUI (optional) |
| audacity | UNAVAILABLE | EXTERNAL | Waveform/spectrogram (optional) |
| rar / unrar | UNAVAILABLE | OPTIONAL | Archive analysis (optional) |
| pyinstaller | UNAVAILABLE | REFERENCE | PE/packed analysis (optional) |

## Python libraries

| Lib | Version | Role |
|-----|---------|------|
| PySide6 | 6.11.2 | GUI |
| numpy | 2.3.5 | audio/video/entropy numerics |
| Pillow | 12.3.0 | image loading |
| cryptography | 50.0.1 | AES-256-GCM + PBKDF2 |
| scapy | 2.7.0 | network laboratory |

## Steganography techniques

| Domain | Technique | Status | Notes |
|--------|-----------|--------|-------|
| Text | LSB + Key | IMPLEMENTED | Native, CRC + key ordering; verified. |
| Image | Native LSB | IMPLEMENTED | Lossless PNG/BMP, verified after write. |
| Image | Steghide | INTEGRATED | Real external tool. |
| Image | CyberHide | REFERENCE | Detected/documented only. |
| Audio | LSB | IMPLEMENTED | SNR measured and reported. |
| Audio | Phase coding | IMPLEMENTED | Robust; SNR may be negative by design. |
| Audio | Spread spectrum | IMPLEMENTED | PN chips; processing-gain trade-off. |
| Audio | Metadata | INTEGRATED | ExifTool on a copy. |
| Audio | DeepSound / CoagulaLight | REFERENCE | Course tools; not re-implemented. |
| Video | FFV1 LSB | IMPLEMENTED | Frame-level, ffmpeg-backed. |
| Video | Custom EOF container | IMPLEMENTED | AES-256-GCM; NOT OpenPuff-compatible. |
| Video | Spread spectrum | IMPLEMENTED | Differential recovery. |
| Video | OpenPuff | REFERENCE | External only. |
| Network | IPv4-ID / UDP covert | IMPLEMENTED | Lab-gated (loopback/RFC1918), root required. |
| Network | pcap interpreter | IMPLEMENTED | Anomaly != proof; teaching text included. |
| Malware | Static analysis | IMPLEMENTED | Defensive only; never executes specimens. |
| Executable | PE overlay payload | IMPLEMENTED | AES-256-GCM blob appended after the last section; never executed. |
| Executable | Section slack-space hiding | IMPLEMENTED | Output keeps the exact carrier size; detected by the static scanner. |
