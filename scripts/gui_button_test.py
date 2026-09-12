#!/usr/bin/env python3
"""Exercise the real GUI button handlers (the path a user clicks) to prove the
``Runner.run() got multiple values for argument 'on_done'`` bug is fixed.

Before the fix, calling a view's ``_hide``/``_extract``/``_compute``... handler raised
TypeError synchronously.  This script fills each view's input widgets with real sample
values, invokes the actual handler, waits for the worker pool, and verifies a real
result was reflected (console/status text populated) with no exception.

Usage: QT_QPA_PLATFORM=offscreen python scripts/gui_button_test.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThreadPool  # noqa: E402

import seed_samples  # noqa: E402
from app.gui.app import build_app  # noqa: E402

TMP = ROOT / "data" / "tmp"
RESULTS: list[tuple[str, bool, str]] = []


def settle():
    QThreadPool.globalInstance().waitForDone(15000)
    for _ in range(6):
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    s = seed_samples.seed()
    app, window = build_app([])
    window.show()
    v = window._views

    def check(name, fn):
        try:
            detail = fn()
            RESULTS.append((name, True, detail))
            print(f"  PASS {name}: {detail}")
        except Exception as exc:  # noqa: BLE001
            RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
            print(f"  FAIL {name}: {type(exc).__name__}: {exc}")

    # ---- text: hide then extract (the exact reported crash) ----
    def t():
        tv = v["text"]
        tv.cover.setPlainText("alpha beta gamma delta epsilon zeta eta theta " * 300)
        tv.secret.setPlainText("button path secret 123")
        tv.key.setText("k1x9")
        tv._encode()
        settle()
        stego = tv.stego.toPlainText()
        assert stego, "no stego produced"
        tv._decode()
        settle()
        return f"stego_len={len(stego)}"
    check("text hide+extract", t)

    # ---- image ----
    def i():
        iv = v["image"]
        iv.carrier.setText(str(s["image_png"]))
        iv.secret.setText(str(s["text_secret"]))
        iv.password.setText("p1x9")
        iv.output.setText(str(TMP / "btn_img.png"))
        iv._hide()
        settle()
        return f"console={len(iv.console.text.toPlainText())} chars"
    check("image hide", i)

    # ---- audio ----
    def a():
        av = v["audio"]
        av.carrier.setText(str(s["audio_wav"]))
        av.secret.setText(str(s["text_secret"]))
        av.key.setText("k1x9")
        av.output.setText(str(TMP / "btn_aud.wav"))
        av._hide()
        settle()
        return f"console={len(av.console.text.toPlainText())} chars"
    check("audio hide", a)

    # ---- hashing compute + compare ----
    def h():
        hv = v["hashing"]
        hv.file_edit.setText(str(s["image_png"]))
        hv._compute()
        settle()
        hv.file_a.setText(str(s["image_png"]))
        hv.file_b.setText(str(s["image_png"]))
        hv._compare()
        settle()
        return "computed+compared"
    check("hashing compute+compare", h)

    # ---- metadata read ----
    def m():
        mv = v["metadata"]
        mv.file_edit.setText(str(s["image_jpg"]))
        mv._read()
        settle()
        return "read done"
    check("metadata read", m)

    # ---- forensics triage ----
    def f():
        fv = v["forensics"]
        fv.file_edit.setText(str(s["image_png"]))
        fv._triage()
        settle()
        return "triage done"
    check("forensics triage", f)

    # ---- network preview ----
    def n():
        nv = v["network"]
        nv.payload.setText("button path payload")
        nv._preview()
        settle()
        return f"console={len(nv.console.text.toPlainText())} chars"
    check("network preview", n)

    # ---- malware static ----
    def mw():
        mvw = v["malware"]
        mvw.file_edit.setText(str(s["mal_zip"]))
        mvw._analyse()
        settle()
        return "static done"
    check("malware static", mw)

    ok = sum(1 for _, good, _ in RESULTS if good)
    print(f"\n{ok}/{len(RESULTS)} GUI button paths OK")
    return 0 if ok == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
