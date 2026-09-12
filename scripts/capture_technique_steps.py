#!/usr/bin/env python3
"""Execute each technique through the REAL services and reflect the result in the matching GUI view.

For every step we (1) run the real service, (2) push the genuine result into the view's own
callback so the UI shows the measured values, (3) grab a screenshot.  A result, each screenshot
shows a real, populated UI state produced by a real operation.

Usage: QT_QPA_PLATFORM=offscreen python scripts/capture_technique_steps.py <out_dir>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThreadPool  # noqa: E402

import seed_samples  # noqa: E402
from app.gui.app import build_app  # noqa: E402

TMP = ROOT / "data" / "tmp"


def settle(app, window):
    QThreadPool.globalInstance().waitForDone(15000)
    for _ in range(5):
        app.processEvents()


def grab(window, out, name):
    path = out / name
    window.grab().save(str(path))
    return path.exists()


def main() -> int:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    samples = seed_samples.seed()
    app, window = build_app([])
    window.resize(1440, 900); window.show()
    views = window._views

    ok_count = 0

    def do(nav, name, work):
        nonlocal ok_count
        window.navigate(nav)
        view = views[nav]
        try:
            work(view)
            settle(app, window)
            if grab(window, out, name):
                ok_count += 1
        except Exception as exc:  # noqa: BLE001 - honest failure
            print(f"  FAIL {name}: {exc}")

    # ---- Text
    from app.modules.text import service as T

    def text_step(v):
        cover = samples["text_cover"].read_text()
        hid = T.hide(cover, "Step secret 0123456789", "step-key")
        v._encoded(hid)
    do("text", "24_text_encode.png", text_step)

    def text_dec(v):
        cover = samples["text_cover"].read_text()
        hid = T.hide(cover, "Step secret 0123456789", "step-key")
        dec = T.extract(hid["stego_text"], "step-key")
        v._decoded(dec)
    do("text", "25_text_decode.png", text_dec)

    # ---- Image
    from app.modules.image import service as I

    def img_hide(v):
        hid = I.native_embed(samples["image_png"], samples["text_secret"],
                             "img-step", TMP / "step_stego.png", 3)
        v._hidden(hid)
    do("image", "26_image_hide.png", img_hide)

    def img_ext(v):
        hid = I.native_embed(samples["image_png"], samples["text_secret"],
                             "img-step", TMP / "step_stego.png", 3)
        ext = I.native_extract(TMP / "step_stego.png", "img-step", TMP / "step_out.txt")
        v._extracted(ext)
    do("image", "27_image_extract.png", img_ext)

    # ---- Audio
    from app.modules.audio import service as A

    def aud_hide(v):
        hid = A.lsb_hide(samples["audio_wav"], samples["text_secret"],
                           "aud-step", TMP / "step_a.wav")
        v._hidden(hid)
    do("audio", "28_audio_hide.png", aud_hide)

    def aud_ext(v):
        A.lsb_hide(samples["audio_wav"], samples["text_secret"],
                  "aud-step", TMP / "step_a.wav")
        ext = A.lsb_extract(TMP / "step_a.wav", "aud-step", TMP / "step_a_out.txt")
        v._extracted(ext)
    do("audio", "29_audio_extract.png", aud_ext)

    # ---- Video
    from app.modules.video import service as V

    def vid_hide(v):
        hid = V.container_hide(samples["video_mp4"], samples["text_secret"],
                              "vid-step", TMP / "step_c.mp4")
        v._hidden(hid)
    do("video", "30_video_hide.png", vid_hide)

    def vid_det(v):
        V.container_hide(samples["video_mp4"], samples["text_secret"],
                         "vid-step", TMP / "step_c.mp4")
        det = V.container_detect(TMP / "step_c.mp4")
        v._detected(det)
    do("video", "31_video_detect.png", vid_det)

    # ---- Network
    from app.modules.network import service as N

    def net_prev(v):
        prev = N.encode_preview(b"network step payload")
        v.console.set_text("\n".join(str(x) for x in prev["notes"]))
    do("network", "32_network_preview.png", net_prev)

    def net_ana(v):
        an = N.analyse_capture(samples["net_covert"])
        v._analysed(an)
    do("network", "33_network_analyse.png", net_ana)

    # ---- Malware
    from app.modules.malware import service as M

    def mal(v):
        r = M.static_analysis(samples["mal_zip"])
        v._done(r)
    do("malware", "34_malware_static.png", mal)

    def exec_hide(v):
        out_s = TMP / "step_exec_slack.exe"
        out_s.unlink(missing_ok=True)
        v.file_edit.setText(str(samples["pe_carrier"]))
        v.payload_edit.setText(str(samples["text_secret"]))
        v.key_edit.setText("StepKey1")
        v.technique_combo.setCurrentIndex(1)
        v.output_edit.setText(str(out_s))
        r = M.executable_hide(samples["pe_carrier"], samples["text_secret"],
                              out_s, "StepKey1", "slack")
        v._hide_done(r)
        TMP.joinpath("step_exec_ref.txt").write_text(str(out_s))
    do("malware", "34b_exec_stego_hide.png", exec_hide)

    def exec_scan(v):
        r = M.executable_scan(Path(TMP.joinpath("step_exec_ref.txt").read_text()))
        v._scan_done(r)
    do("malware", "34c_exec_stego_scan.png", exec_scan)

    def exec_extract(v):
        r = M.executable_extract(Path(TMP.joinpath("step_exec_ref.txt").read_text()),
                                 TMP / "step_exec_out", "StepKey1")
        v._extract_done(r)
    do("malware", "34d_exec_stego_extract.png", exec_extract)

    # ---- Metadata
    from app.modules.metadata import service as MD

    def meta_read(v):
        snap = MD.read(samples["image_jpg"])
        v._loaded(snap)
    do("metadata", "35_metadata_read.png", meta_read)

    def meta_inj(v):
        res = MD.inject(samples["image_jpg"], {"Comment": "step", "Author": "QA"},
                           TMP / "step_inj.jpg")
        # Reflect tags + before/after without triggering the async re-read.
        snap = MD.read(TMP / "step_inj.jpg")
        v._loaded(snap)
        v.hash_line.setText(f"before {res['original_sha256'][:20]}... after {res['output_sha256'][:20]}...")
    do("metadata", "36_metadata_inject.png", meta_inj)

    # ---- Hashing
    from app.modules.hashing import service as H

    def hash_comp(v):
        r = H.hash_file(samples["image_png"])
        v._computed(r)
    do("hashing", "37_hashing_compute.png", hash_comp)

    def hash_cmp(v):
        r = H.verify(samples["image_png"], samples["image_png"])
        v._compared({"identical": r["match"], "size_delta": 0,
                           "conclusion": r["assessment"]})
    do("hashing", "38_hashing_compare.png", hash_cmp)

    # ---- Forensics
    from app.modules.forensics import service as F

    def fore(v):
        r = F.triage(samples["image_png"])
        v._triage_done(r)
    do("forensics", "39_forensics_triage.png", fore)

    print(f"captured {ok_count} step screenshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
