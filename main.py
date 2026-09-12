#!/usr/bin/env python3
"""StegoNexus - integrated steganography investigation workstation.

Usage:
    python main.py                # launch the PySide6 GUI
    python main.py --cli          # launch the interactive text interface
    python main.py --diagnostics  # print the live tool health matrix
    python main.py --version
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import APP_NAME, __version__  # noqa: E402
from app.core.config import get_config  # noqa: E402
from app.core.exceptions import StegoNexusError  # noqa: E402
from app.core.logger import get_logger, setup_logging  # noqa: E402

LOG = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="stegonexus",
        description=f"{APP_NAME} {__version__} - hide, extract, analyze, verify, "
                    "investigate, document and report.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--cli", action="store_true", help="run the interactive text interface")
    mode.add_argument("--diagnostics", action="store_true",
                      help="print the live tool health matrix and exit")
    mode.add_argument("--version", action="store_true", help="print version and exit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.version:
        print(f"{APP_NAME} {__version__}")
        return 0

    config = get_config()
    setup_logging(verbose=settings_verbose(config) or None)
    LOG.info("StegoNexus %s starting (cli=%s diagnostics=%s)",
             __version__, args.cli, args.diagnostics)

    if args.diagnostics:
        from app.gui.app import run_diagnostics
        return run_diagnostics()

    if args.cli:
        from app.cli.app import run_cli
        return run_cli()

    from app.gui.app import run_gui
    return run_gui()


def settings_verbose(config) -> bool:
    try:
        from app.modules.settings import service as settings

        return bool(settings.current().get("verbose_logs", False))
    except Exception:  # settings not yet readable: default to concise logs
        return False


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StegoNexusError as exc:
        print(f"\nOperation failed\nReason: {exc}\n"
              f"Suggested action: {getattr(exc, 'suggestion', 'see logs/stegonexus.log')}",
              file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
