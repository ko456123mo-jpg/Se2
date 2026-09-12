#!/usr/bin/env python3
"""Headless GUI smoke test.

Builds the real MainWindow on the Qt ``offscreen`` platform, navigates to every
registered view, lets background workers finish, and saves a PNG screenshot of each
view. Any exception, or any view that fails to paint, fails the run - so the pictures
in ``presentation/screenshots`` always come from the implemented application.

Usage:
    QT_QPA_PLATFORM=offscreen python scripts/gui_smoke_test.py
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.gui.app import build_app  # noqa: E402
from app.gui.main_window import NAV_GROUPS  # noqa: E402
from app.gui.views.registry import VIEW_FACTORIES  # noqa: E402

SHOTS = ROOT / "presentation" / "screenshots"


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)

    # Deterministic capture: dark theme for the gallery, light for the toggle shot.
    from app.modules.settings import service as settings
    settings.save(theme="dark")

    app, window = build_app([])
    window.resize(1440, 900)
    window.show()

    nav_ids = [view_id for _, entries in NAV_GROUPS for view_id, _, _ in entries]
    missing = [nav_id for nav_id in nav_ids if nav_id not in VIEW_FACTORIES]
    print(f"nav items: {len(nav_ids)}  registered views: {len(VIEW_FACTORIES)}  "
          f"missing: {missing or 'none'}")

    failures: list[str] = []
    for nav_id in nav_ids:
        try:
            window.navigate(nav_id)
            QThreadPool.globalInstance().waitForDone(20000)
            for _ in range(6):
                app.processEvents()
            # navigate() turns refresh errors into a toast, so call refresh directly too.
            view = window._views[nav_id]
            view.refresh()
            QThreadPool.globalInstance().waitForDone(20000)
            for _ in range(4):
                app.processEvents()
            window.grab().save(str(SHOTS / f"{nav_id}.png"))
            title = view.title
            print(f"  PASS  {nav_id:<12} -> {title}")
        except Exception:  # noqa: BLE001 - the smoke test must report every failure
            failures.append(nav_id)
            print(f"  FAIL  {nav_id}")
            traceback.print_exc()

    # Exercise the theme switch on a populated view.
    try:
        window.navigate("dashboard")
        window._toggle_theme()
        QThreadPool.globalInstance().waitForDone(20000)
        app.processEvents()
        window.grab().save(str(SHOTS / "dashboard-light.png"))
        print("  PASS  theme toggle -> dashboard-light.png")
        # Leave the persisted theme back on dark (the shipping default).
        settings.save(theme="dark")
    except Exception:  # noqa: BLE001
        failures.append("theme-toggle")
        traceback.print_exc()

    # Extra evidence shot: executable steganography (hide + detect) in action.
    try:
        import seed_samples  # noqa: PLC0415
        from app.modules.malware import service as malware_svc  # noqa: PLC0415

        samples = seed_samples.seed()
        out_s = ROOT / "data" / "tmp" / "smoke_exec_slack.exe"
        out_s.unlink(missing_ok=True)
        hidden = malware_svc.executable_hide(samples["pe_carrier"],
                                             samples["text_secret"], out_s,
                                             "SmokeKey1", "slack")
        scanned = malware_svc.executable_scan(out_s)
        window.navigate("malware")
        view = window._views["malware"]
        view.file_edit.setText(str(samples["pe_carrier"]))
        view._hide_done(hidden)
        view._scan_done(scanned)
        QThreadPool.globalInstance().waitForDone(20000)
        for _ in range(6):
            app.processEvents()
        window.grab().save(str(SHOTS / "malware_exec_stego.png"))
        print("  PASS  executable stego -> malware_exec_stego.png")
    except Exception:  # noqa: BLE001
        failures.append("exec-stego-shot")
        traceback.print_exc()

    print(f"\nscreenshots: {SHOTS}")
    print(f"{'SMOKE TEST PASSED' if not failures else 'SMOKE TEST FAILED'} "
          f"({len(nav_ids) - len(failures)}/{len(nav_ids)} views)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
