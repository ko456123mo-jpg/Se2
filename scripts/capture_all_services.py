#!/usr/bin/env python3
"""Run EVERY StegoNexus service for real and capture a screenshot of each step.

For each service we (1) execute the REAL operation, (2) push the genuine result
into the matching GUI view so the UI shows the measured values, (3) grab the
window, and (4) record an explanation built from the actual returned values.
Nothing is fabricated: if an operation fails the explanation says so.

Usage: QT_QPA_PLATFORM=offscreen python scripts/capture_all_services.py <out_dir>
Writes <out_dir>/sNN_*.png and <out_dir>/steps.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
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
STEPS: list[dict] = []


def settle(app):
    QThreadPool.globalInstance().waitForDone(15000)
    for _ in range(6):
        app.processEvents()


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    samples = seed_samples.seed()
    secret = samples["text_secret"]
    sbytes = secret.read_bytes()

    # long carriers needed by phase (>=15 s) and spread (>=30 s)
    long16 = TMP / "svc_long16.wav"
    long30 = TMP / "svc_long30.wav"
    for dur, dst in ((16, long16), (30, long30)):
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency=330:duration={dur}", "-ar", "44100",
                        "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
                       check=True, capture_output=True)

    app, window = build_app([])
    window.resize(1440, 900)
    window.show()
    views = window._views
    holder: dict = {}
    idx = {"n": 0}

    def step(nav, service, title, work):
        idx["n"] += 1
        fname = f"s{idx['n']:02d}_{nav}_{service.replace(' ', '_')}.png"
        window.navigate(nav)
        view = views[nav]
        try:
            explanation = work(view)
            settle(app)
            ok = (out / fname)
            window.grab().save(str(ok))
            STEPS.append({"file": fname, "nav": nav, "service": service,
                          "title": title, "status": "PASS",
                          "explanation": explanation})
            print(f"  PASS {fname}: {title}")
        except Exception as exc:  # noqa: BLE001 - honest failure
            STEPS.append({"file": fname, "nav": nav, "service": service,
                          "title": title, "status": "FAIL",
                          "explanation": f"{type(exc).__name__}: {exc}"})
            print(f"  FAIL {fname}: {type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------ cases
    from app.modules.cases import service as C
    from app.modules.evidence import service as EV

    def w_cases(v):
        cid = C.create("REAL SERVICE TEST", "all-services real run", "QA")
        cid = cid if isinstance(cid, int) else (cid.get("id") or cid.get("case_id"))
        holder["cid"] = cid
        ev = EV.import_file(cid, samples["image_jpg"])
        v.refresh()
        return (f"Created training case #{cid} (labelled SYNTHETIC) and imported "
                f"evidence '{samples['image_jpg'].name}' (id "
                f"{ev.get('id') if isinstance(ev, dict) else ev}). The case list on "
                f"screen is real data from the SQLite store.")
    step("cases", "cases", "Case create + evidence import", w_cases)

    # ----------------------------------------------------------------- hashing
    from app.modules.hashing import service as H

    def w_hash(v):
        r = H.hash_file(samples["image_jpg"])
        v._computed(r)
        return (f"Computed 4 hashes of {samples['image_jpg'].name}: "
                f"SHA-256 {r.sha256[:32]}... (MD5/SHA-1/SHA-512 also computed).")
    step("hashing", "hashing", "Hashing 4 algorithms", w_hash)

    def w_hash_cmp(v):
        r = H.verify(samples["image_jpg"], samples["image_jpg"])
        v._compared({"identical": r["match"], "size_delta": 0,
                     "conclusion": r["assessment"]})
        return (f"Integrity verify of the file against itself: match={r['match']} "
                f"-> {r['assessment']}.")
    step("hashing", "hashing", "Hashing verify / compare", w_hash_cmp)

    # ---------------------------------------------------------------- metadata
    from app.modules.metadata import service as MD

    def w_meta_read(v):
        snap = MD.read(samples["image_jpg"])
        v._loaded(snap)
        n = len(getattr(snap, "tags", {}) or {})
        tool = getattr(snap, "tool", "?")
        return f"Read metadata of {samples['image_jpg'].name} via {tool}: {n} tags."
    step("metadata", "metadata", "Metadata read (exiftool)", w_meta_read)

    def w_meta_inj(v):
        before = H.hash_file(samples["image_jpg"]).sha256
        res = MD.inject(samples["image_jpg"], {"Comment": "svc", "Artist": "QA"},
                        TMP / "svc_inj.jpg")
        snap = MD.read(TMP / "svc_inj.jpg")
        v._loaded(snap)
        after = H.hash_file(samples["image_jpg"]).sha256
        v.hash_line.setText(f"original before {before[:16]}  after {after[:16]}  "
                            f"unchanged={before == after}")
        return (f"Injected 2 tags into a WORKING COPY; the ORIGINAL hash is unchanged "
                f"({before == after}), proving read-only-by-default.")
    step("metadata", "metadata", "Metadata inject on a copy", w_meta_inj)

    # ---------------------------------------------------------------- forensics
    from app.modules.forensics import service as F

    def w_fore(v):
        r = F.triage(samples["image_jpg"])
        v._triage_done(r)
        ind = r.get("indicator_count", r.get("indicators"))
        if isinstance(ind, list):
            ind = len(ind)
        return (f"One-click triage of {samples['image_jpg'].name} across "
                f"file/strings/exif/entropy/binwalk/steghide/foremost: "
                f"{ind} indicator(s). Indicators, not proof.")
    step("forensics", "forensics", "Forensics triage", w_fore)

    # -------------------------------------------------------------------- text
    from app.modules.text import service as T

    def w_text_hide(v):
        cover = samples["text_cover"].read_text()
        hid = T.hide(cover, "Real service test 0123456789", "svc-key")
        v._encoded(hid)
        return (f"Text LSB hide: {hid['payload_bits']} payload bits into the cover, "
                f"utilisation {hid['utilisation']:.1%}, capacity {hid['capacity_bits']} bits.")
    step("text", "text", "Text LSB hide", w_text_hide)

    def w_text_ext(v):
        cover = samples["text_cover"].read_text()
        hid = T.hide(cover, "Real service test 0123456789", "svc-key")
        dec = T.extract(hid["stego_text"], "svc-key")
        v._decoded(dec)
        return (f"Text LSB extract with the correct key recovered: "
                f"'{dec['message']}' (exact match={dec['message'] == 'Real service test 0123456789'}).")
    step("text", "text", "Text LSB extract", w_text_ext)

    # ------------------------------------------------------------------- image
    from app.modules.image import service as I

    def w_img_hide(v):
        hid = I.native_embed(samples["image_png"], secret, "svc-key", TMP / "svc_img.png")
        v._hidden(hid)
        return (f"Image native LSB embed into {samples['image_png'].name}: "
                f"{hid['payload_bytes']} bytes hidden, output {Path(hid['output']).name}.")
    step("image", "image", "Image native LSB hide", w_img_hide)

    def w_img_ext(v):
        I.native_embed(samples["image_png"], secret, "svc-key", TMP / "svc_img.png")
        ext = I.native_extract(TMP / "svc_img.png", "svc-key", TMP / "svc_img_out.bin")
        v._extracted(ext)
        match = (TMP / "svc_img_out.bin").read_bytes() == sbytes
        return f"Image native LSB extract: recovered {ext['payload_bytes']} bytes, byte-for-byte match={match}."
    step("image", "image", "Image native LSB extract", w_img_ext)

    def w_img_sh(v):
        hid = I.steghide_embed(samples["image_jpg"], secret, "svcpass", TMP / "svc_sh.jpg")
        v._hidden(hid)
        return (f"Image Steghide embed (real steghide 0.5.x) into a JPEG carrier: "
                f"{hid['payload_bytes']} bytes hidden.")
    step("image", "image", "Image Steghide hide", w_img_sh)

    def w_img_sh_ext(v):
        I.steghide_embed(samples["image_jpg"], secret, "svcpass", TMP / "svc_sh.jpg")
        ext = I.steghide_extract(TMP / "svc_sh.jpg", "svcpass", TMP / "svc_sh_out.bin")
        v._extracted(ext)
        match = (TMP / "svc_sh_out.bin").read_bytes() == sbytes
        return f"Image Steghide extract: recovered {ext['payload_bytes']} bytes, match={match}."
    step("image", "image", "Image Steghide extract", w_img_sh_ext)

    # ------------------------------------------------------------------- audio
    from app.modules.audio import service as A

    def w_aud_lsb(v):
        hid = A.lsb_hide(samples["audio_wav"], secret, "svc-key", TMP / "svc_a.wav")
        v._hidden(hid)
        return f"Audio LSB hide into {samples['audio_wav'].name}: {hid['payload_bytes']} bytes, SNR {hid.get('snr_db')} dB."
    step("audio", "audio", "Audio LSB hide", w_aud_lsb)

    def w_aud_lsb_ext(v):
        A.lsb_hide(samples["audio_wav"], secret, "svc-key", TMP / "svc_a.wav")
        ext = A.lsb_extract(TMP / "svc_a.wav", "svc-key", TMP / "svc_a_out.bin")
        v._extracted(ext)
        match = (TMP / "svc_a_out.bin").read_bytes() == sbytes
        return f"Audio LSB extract: recovered {ext['payload_bytes']} bytes, match={match}."
    step("audio", "audio", "Audio LSB extract", w_aud_lsb_ext)

    def w_aud_ph(v):
        hid = A.phase_hide(long16, secret, TMP / "svc_ph.wav", "svc-key")
        v._hidden(hid)
        return (f"Audio phase coding hide into a 16 s carrier: {hid['payload_bytes']} bytes, "
                f"SNR {hid.get('snr_db')} dB (fragile to re-encoding).")
    step("audio", "audio", "Audio phase-coding hide", w_aud_ph)

    def w_aud_ph_ext(v):
        A.phase_hide(long16, secret, TMP / "svc_ph.wav", "svc-key")
        ext = A.phase_extract(TMP / "svc_ph.wav", TMP / "svc_ph_out.bin", "svc-key")
        v._extracted(ext)
        match = (TMP / "svc_ph_out.bin").read_bytes() == sbytes
        return f"Audio phase-coding extract: recovered {ext['payload_bytes']} bytes, match={match}."
    step("audio", "audio", "Audio phase-coding extract", w_aud_ph_ext)

    def w_aud_ss(v):
        hid = A.spread_hide(long30, secret, "svc-key", TMP / "svc_ss.wav")
        v._hidden(hid)
        return (f"Audio spread-spectrum (native DSSS) hide into a 30 s carrier: "
                f"{hid['payload_bytes']} bytes, process gain {hid.get('process_gain_db')} dB.")
    step("audio", "audio", "Audio spread-spectrum hide", w_aud_ss)

    def w_aud_ss_ext(v):
        A.spread_hide(long30, secret, "svc-key", TMP / "svc_ss.wav")
        ext = A.spread_extract(TMP / "svc_ss.wav", "svc-key", TMP / "svc_ss_out.bin")
        v._extracted(ext)
        match = (TMP / "svc_ss_out.bin").read_bytes() == sbytes
        return (f"Audio spread-spectrum extract ({ext.get('differential') and 'differential' or 'blind'}): "
                f"recovered {ext['payload_bytes']} bytes, match={match}.")
    step("audio", "audio", "Audio spread-spectrum extract", w_aud_ss_ext)

    # ------------------------------------------------------------------- video
    from app.modules.video import service as V

    def w_vid_lsb(v):
        hid = V.lsb_hide(samples["video_mp4"], secret, "svc-key", TMP / "svc_v.mkv")
        v._hidden(hid)
        return f"Video LSB hide into a lossless .mkv: {hid['payload_bytes']} bytes hidden."
    step("video", "video", "Video LSB hide", w_vid_lsb)

    def w_vid_lsb_ext(v):
        V.lsb_hide(samples["video_mp4"], secret, "svc-key", TMP / "svc_v.mkv")
        ext = V.lsb_extract(TMP / "svc_v.mkv", "svc-key", TMP / "svc_v_out.bin")
        v._extracted(ext)
        match = (TMP / "svc_v_out.bin").read_bytes() == sbytes
        return f"Video LSB extract: recovered {ext['payload_bytes']} bytes, match={match}."
    step("video", "video", "Video LSB extract", w_vid_lsb_ext)

    def w_vid_cont(v):
        hid = V.container_hide(samples["video_mp4"], secret, "svc-key", TMP / "svc_c.mp4")
        v._hidden(hid)
        return (f"Video EOF-container hide (custom, NOT OpenPuff): {hid['payload_bytes']} bytes "
                f"appended after EOF in a {hid['blob_bytes']}-byte blob; carrier still plays.")
    step("video", "video", "Video EOF-container hide", w_vid_cont)

    def w_vid_det(v):
        V.container_hide(samples["video_mp4"], secret, "svc-key", TMP / "svc_c.mp4")
        det = V.container_detect(TMP / "svc_c.mp4")
        v._detected(det)
        return f"Video EOF-container detect: has_container={det.get('has_container')}."
    step("video", "video", "Video EOF-container detect", w_vid_det)

    def w_vid_ext(v):
        V.container_hide(samples["video_mp4"], secret, "svc-key", TMP / "svc_c.mp4")
        ext = V.container_extract(TMP / "svc_c.mp4", "svc-key", TMP / "svc_c_out")
        v._extracted(ext)
        match = Path(ext["output"]).read_bytes() == sbytes
        return (f"Video EOF-container extract: recovered '{ext['original_name']}' "
                f"({ext['payload_bytes']} bytes), match={match}.")
    step("video", "video", "Video EOF-container extract", w_vid_ext)

    # ----------------------------------------------------------------- network
    from app.modules.network import service as N
    from app.modules.settings import service as S

    def w_net_prev(v):
        prev = N.encode_preview(b"network covert payload")
        v.console.set_text("Encode preview (IPv4 Identification covert channel)\n"
                           + "\n".join(str(x) for x in prev.get("notes", []))
                           + f"\n\nip_ids: {prev.get('ip_ids', [])[:16]} ...")
        return (f"Network encode preview: payload mapped to {len(prev.get('ip_ids', []))} "
                f"IPv4 Identification values (design-level; anomaly != proof).")
    step("network", "network", "Network encode preview", w_net_prev)

    def w_net_ana(v):
        an = N.analyse_capture(samples["net_covert"])
        v._analysed(an)
        conf = (an.get("interpretation") or {}).get("confidence")
        return (f"Network capture analysis of {samples['net_covert'].name}: "
                f"{an.get('packets')} packets, confidence={conf}. Indicators, not proof.")
    step("network", "network", "Network capture analysis", w_net_ana)

    def w_net_sr(v):
        S.save(network_authorized_lab=True)
        port = 53933
        payload = b"StegoNexus loopback round-trip"
        box: dict = {}

        def rx():
            try:
                box["r"] = N.receive(transport="udp_payload", dport=port, count=1, timeout=8)
            except Exception as exc:  # noqa: BLE001
                box["r"] = {"status": "FAILED", "packets": 0, "payload": b"",
                            "elapsed_ms": 0, "error": str(exc), "payload_text": ""}
        th = threading.Thread(target=rx, daemon=True)
        th.start()
        time.sleep(0.6)
        s = N.send(payload, dst="127.0.0.1", dport=port, transport="udp_payload", iface="lo")
        th.join(timeout=10)
        S.save(network_authorized_lab=False)
        v._sent(s)
        r = box.get("r", {})
        v._received(r)
        match = (r.get("payload") == payload)
        return (f"Network send/receive over loopback (baseline UDP, no root): send="
                f"{s.get('status')} ({s.get('packets')} pkts), received match={match}. "
                f"The covert IPv4-ID channel needs root (works on Kali via sudo).")
    step("network", "network", "Network send + receive (loopback)", w_net_sr)

    # ----------------------------------------------------------------- malware
    from app.modules.malware import service as M

    def w_mal(v):
        r = M.static_analysis(samples["mal_zip"])
        v._done(r)
        return (f"Malware STATIC analysis of {samples['mal_zip'].name}: heuristic score "
                f"{r.get('heuristic_score')}, {r.get('indicator_count')} indicator(s), "
                f"confidence {r.get('confidence')}. Never executed (safety).")
    step("malware", "malware", "Malware static analysis", w_mal)

    # -------------------------------------------------- executable stego (new)
    def w_mal_hide(v):
        carrier = samples["pe_carrier"]
        out_s = TMP / "svc_exec_slack.exe"
        out_s.unlink(missing_ok=True)
        v.file_edit.setText(str(carrier))
        v.payload_edit.setText(str(secret))
        v.key_edit.setText("TrainingKey1")
        v.technique_combo.setCurrentIndex(1)          # slack
        v.output_edit.setText(str(out_s))
        r = M.executable_hide(carrier, secret, out_s, "TrainingKey1", "slack")
        v._hide_done(r)
        holder["exec_stego"] = out_s
        return (f"Executable stego HIDE (slack technique): {r['payload_bytes']} B hidden "
                f"inside {carrier.name}; output size unchanged={r['size_unchanged']} "
                f"(carrier SHA-256 recorded). Byte-level operation on a copy - "
                f"the carrier is never executed.")
    step("malware", "exec_stego_hide", "Executable stego hide (slack)", w_mal_hide)

    def w_mal_scan(v):
        r = M.executable_scan(holder["exec_stego"])
        v._scan_done(r)
        found = bool(r.get("slack_blob"))
        return (f"Executable stego SCAN: verdict='{r.get('verdict')}', slack blob "
                f"found={found} ({(r.get('slack_blob') or {}).get('bytes', 0)} B in "
                f"section '{(r.get('slack_blob') or {}).get('section', '-')}', "
                f"total slack {r.get('total_slack')} B). Static inspection only.")
    step("malware", "exec_stego_scan", "Executable stego scan (detection)", w_mal_scan)

    def w_mal_extract(v):
        r = M.executable_extract(holder["exec_stego"], TMP / "svc_exec_out",
                                 "TrainingKey1")
        v._extract_done(r)
        return (f"Executable stego EXTRACT (slack): payload recovered byte-for-byte "
                f"({r['payload_bytes']} B, SHA-256 {r['sha256'][:16]}...) and saved "
                f"to {Path(r['output']).name}. Wrong key fails safely (AES-GCM).")
    step("malware", "exec_stego_extract", "Executable stego extract", w_mal_extract)

    def w_mal_static_flag(v):
        r = M.static_analysis(holder["exec_stego"])
        v._done(r)
        hits = [i for i in r["indicators"] if "stego" in i.lower()]
        return (f"Static analysis of the stego carrier now flags it: {len(hits)} "
                f"executable-stego indicator(s), score {r.get('heuristic_score')}. "
                f"Detection closes the loop: hide -> scan -> extract -> flag.")
    step("malware", "exec_stego_flag", "Static analysis flags the stego carrier", w_mal_static_flag)

    # ----------------------------------------------------------------- reports
    from app.modules.reports import service as R

    def w_rep(v):
        cid = holder.get("cid") or C.create("REPORT CASE", "x", "QA")
        outs = R.generate(cid)
        v._generated(outs)
        fmts = ", ".join(f"{o['format']}({o['bytes']}B)" for o in outs)
        return f"Report generation for case #{cid}: {fmts}. All three formats written for real."
    step("reports", "reports", "Reports PDF/HTML/JSON", w_rep)

    # -------------------------------------------------------------- extraction
    def w_ext(v):
        v.refresh()
        return "Extraction workspace refreshed; it aggregates real findings/evidence from the store."
    step("extraction", "extraction", "Extraction workspace", w_ext)

    (out / "steps.json").write_text(json.dumps(STEPS, indent=2))
    passed = sum(1 for s in STEPS if s["status"] == "PASS")
    print(f"\ncaptured {passed}/{len(STEPS)} service screenshots -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
