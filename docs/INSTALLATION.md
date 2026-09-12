# Installation (Kali / Debian)

## One-command install

```bash
./scripts/install_kali.sh     # apt (binary tools) + pip (Python deps)
```

The script installs the core forensic toolchain (`exiftool`, `steghide`, `binwalk`,
`foremost`, `ffmpeg`, `tshark`, `file`, `binutils`, `p7zip`), best-effort optional tools
(`wireshark`, `audacity`, `rar`, `zsteg`), and the Python requirements. Optional tools
that fail to install are simply reported as **UNAVAILABLE** inside the app - they are
never faked.

## Manual install

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends libimage-exiftool-perl steghide \
    binwalk foremost ffmpeg tshark file binutils p7zip-full
pip install -r requirements.txt
```

## Verify

```bash
python scripts/check_dependencies.py
```

Expected on a full install: all required Python libs `[OK]`, core binaries `[OK]`,
`RESULT: all required dependencies present.` Optional tools may show `[missing]` and are
then reported as UNAVAILABLE.

## Launch

```bash
./scripts/run.sh                # PySide6 GUI
python3 main.py --cli           # interactive text interface
python3 main.py --diagnostics   # print the live tool-health matrix
```

## Desktop integration (optional)

```bash
./scripts/install_desktop.sh    # adds a menu entry + launcher icon
./scripts/uninstall.sh          # removes the desktop entry (data preserved)
```

## Runtime locations

State lives under the project tree (`data/`, `cases/`, `reports/`, `logs/`). Set
`STEGONEXUS_HOME` to relocate. `data/` is created with mode `0700` because it can hold
evidence hashes and settings.
