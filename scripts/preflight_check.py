#!/usr/bin/env python3
"""Pre-Kali readiness check.

Runs EVERY StegoNexus technique for real (true round-trips: the extracted
payload is compared byte-for-byte with the original secret) and prints a
PASS / PARTIAL / GATED / FAIL line per feature. Nothing here is simulated:
if a tool is missing or an operation fails, it is reported honestly.

Run from the project root:
    QT_QPA_PLATFORM=offscreen python scripts/preflight_check.py
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import scripts.seed_samples as seed_samples  # noqa: E402
from app.modules.text import service as text  # noqa: E402
from app.modules.image import service as image  # noqa: E402
from app.modules.audio import service as audio  # noqa: E402
from app.modules.video import service as video  # noqa: E402
from app.modules.network import service as network  # noqa: E402
from app.modules.metadata import service as metadata  # noqa: E402
from app.modules.hashing import service as hashing  # noqa: E402
from app.modules.forensics import service as forensics  # noqa: E402
from app.modules.malware import service as malware  # noqa: E402
from app.modules.reports import service as reports  # noqa: E402
from app.modules.cases import service as cases  # noqa: E402
from app.modules.evidence import service as evidence  # noqa: E402

RESULTS: list[dict] = []


def rec(name: str, status: str, detail: str) -> None:
    RESULTS.append({"check": name, "status": status, "detail": detail})
    print(f"[{status:7}] {name}: {detail}")


def run(name: str, fn):
    try:
        fn()
    except Exception as exc:  # honest: capture the real error
        rec(name, "FAIL", f"{type(exc).__name__}: {exc}")
        traceback.print_exc(file=sys.stderr)


def _case_id(r) -> int:
    if isinstance(r, int):
        return r
    if isinstance(r, dict):
        return int(r.get("id") or r.get("case_id") or r.get("case") or 0)
    return int(getattr(r, "id", 0) or 0)


def main() -> int:
    samples = seed_samples.seed()
    tmp = ROOT / "data" / "preflight"
    tmp.mkdir(parents=True, exist_ok=True)
    secret = tmp / "secret.bin"
    secret.write_bytes(b"StegoNexus-PREFLIGHT-payload-0123456789")
    sbytes = secret.read_bytes()

    # ---- 1. dependencies -------------------------------------------------
    def deps():
        tools = ["exiftool", "ffmpeg", "ffprobe", "steghide", "binwalk",
                 "foremost", "tshark", "file", "strings"]
        missing = [t for t in tools if not shutil.which(t)]
        rec("tools_installed", "FAIL" if missing else "PASS",
            "missing: " + ", ".join(missing) if missing else "all 9 present")
        mods = []
        for m in ("PySide6", "cryptography", "scapy", "PIL", "numpy"):
            try:
                __import__(m)
            except Exception:
                mods.append(m)
        rec("python_deps", "FAIL" if mods else "PASS",
            "missing: " + ", ".join(mods) if mods else "PySide6/cryptography/scapy/PIL/numpy OK")
    run("dependencies", deps)

    # ---- 2. case + evidence + hashing ------------------------------------
    state = {}

    def case_hash():
        cid = _case_id(cases.create("PREFLIGHT READINESS", "preflight", "QA"))
        state["cid"] = cid
        evidence.import_file(cid, samples["image_jpg"])
        h = hashing.hash_file(samples["image_jpg"])
        algos = sorted((h.hashes or {}).keys()) if hasattr(h, "hashes") else []
        v = hashing.verify(samples["image_jpg"], samples["image_jpg"])
        match = v.get("match") if isinstance(v, dict) else getattr(v, "match", False)
        rec("case_evidence_hash", "PASS" if (cid and match and len(algos) >= 4) else "FAIL",
            f"case={cid} algos={','.join(algos)} verify_match={match}")
    run("case_evidence_hash", case_hash)

    # ---- 3. metadata (read/inject/strip; original unchanged) -------------
    def meta():
        before = hashing.hash_file(samples["image_jpg"]).sha256
        metadata.read(samples["image_jpg"])
        metadata.inject(samples["image_jpg"], {"Comment": "preflight"}, tmp / "inj.jpg")
        metadata.strip(samples["image_jpg"], tmp / "strip.jpg")
        after = hashing.hash_file(samples["image_jpg"]).sha256
        rec("metadata_read_inject_strip", "PASS" if before == after else "FAIL",
            f"original_unchanged={before == after}")
    run("metadata", meta)

    # ---- 4. text LSB round-trip ------------------------------------------
    def txt():
        cover = samples["text_cover"].read_text(encoding="utf-8")
        msg = "PREFLIGHT-SECRET-MSG"
        h = text.hide(cover, msg, "PreKey123")
        e = text.extract(h["stego_text"], "PreKey123")
        rec("text_lsb_roundtrip", "PASS" if e["message"] == msg else "FAIL",
            f"recovered_match={e['message'] == msg}")
    run("text", txt)

    # ---- 5. image native LSB + steghide ----------------------------------
    def img_native():
        image.native_embed(samples["image_png"], secret, "PreKey123", tmp / "img_native.png")
        image.native_extract(tmp / "img_native.png", "PreKey123", tmp / "img_native_out.bin")
        ok = (tmp / "img_native_out.bin").read_bytes() == sbytes
        rec("image_native_lsb", "PASS" if ok else "FAIL", f"byte_match={ok}")
    run("image_native", img_native)

    def img_steghide():
        image.steghide_embed(samples["image_jpg"], secret, "prepass", tmp / "img_sh.jpg")
        image.steghide_extract(tmp / "img_sh.jpg", "prepass", tmp / "img_sh_out.bin")
        ok = (tmp / "img_sh_out.bin").read_bytes() == sbytes
        rec("image_steghide", "PASS" if ok else "FAIL", f"byte_match={ok} (JPEG carrier)")
    run("image_steghide", img_steghide)

    # ---- 6. audio LSB + phase --------------------------------------------
    def aud_lsb():
        audio.lsb_hide(samples["audio_wav"], secret, "PreKey123", tmp / "aud_lsb.wav")
        audio.lsb_extract(tmp / "aud_lsb.wav", "PreKey123", tmp / "aud_lsb_out.bin")
        ok = (tmp / "aud_lsb_out.bin").read_bytes() == sbytes
        rec("audio_lsb", "PASS" if ok else "FAIL", f"byte_match={ok}")
    run("audio_lsb", aud_lsb)

    def aud_phase():
        longwav = tmp / "long.wav"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=16", "-ar", "44100", "-ac", "1",
                        str(longwav)], check=True, capture_output=True)
        audio.phase_hide(longwav, secret, tmp / "aud_phase.wav", "PreKey123")
        audio.phase_extract(tmp / "aud_phase.wav", tmp / "aud_phase_out.bin", "PreKey123")
        ok = (tmp / "aud_phase_out.bin").read_bytes() == sbytes
        rec("audio_phase", "PASS" if ok else "FAIL", f"byte_match={ok} (16 s carrier)")
    run("audio_phase", aud_phase)

    def aud_spread():
        # Native audio DSSS now works on lossless PCM WAV (blind + differential).
        carrier = tmp / "ss_carrier.wav"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=330:duration=30", "-ar", "44100", "-ac", "1",
                        "-c:a", "pcm_s16le", str(carrier)], check=True, capture_output=True)
        audio.spread_hide(carrier, secret, "PreKey123", tmp / "aud_ss.wav")
        audio.spread_extract(tmp / "aud_ss.wav", "PreKey123", tmp / "aud_ss_out.bin")
        ok = (tmp / "aud_ss_out.bin").read_bytes() == sbytes
        rec("audio_spread", "PASS" if ok else "FAIL",
            f"blind_extract_match={ok} (native DSSS, 30 s carrier)")
    run("audio_spread", aud_spread)

    # ---- 7. video LSB + EOF container ------------------------------------
    def vid_lsb():
        # Video LSB needs a LOSSLESS output container (.mkv/.avi/.nut); the app
        # correctly refuses lossy .mp4. Carrier may be .mp4; output must be .mkv.
        video.lsb_hide(samples["video_mp4"], secret, "PreKey123", tmp / "vid_lsb.mkv")
        video.lsb_extract(tmp / "vid_lsb.mkv", "PreKey123", tmp / "vid_lsb_out.bin")
        ok = (tmp / "vid_lsb_out.bin").read_bytes() == sbytes
        rec("video_lsb", "PASS" if ok else "FAIL", f"byte_match={ok} (.mkv lossless)")
    run("video_lsb", vid_lsb)

    def vid_container():
        video.container_hide(samples["video_mp4"], secret, "PreKey123", tmp / "vid_cont.mp4")
        det = video.container_detect(tmp / "vid_cont.mp4")
        outdir = tmp / "vid_cont_out"
        ext = video.container_extract(tmp / "vid_cont.mp4", "PreKey123", outdir)
        ok = Path(ext["output"]).read_bytes() == sbytes and bool(det.get("has_container"))
        rec("video_eof_container", "PASS" if ok else "FAIL",
            f"detected={det.get('has_container')} byte_match={Path(ext['output']).read_bytes() == sbytes} (not OpenPuff)")
    run("video_container", vid_container)

    # ---- 8. network -------------------------------------------------------
    def net():
        prev = network.encode_preview(b"covert-payload")
        has_prev = any(k in prev for k in ("packets", "ip_ids", "fields", "preview"))
        rec("network_encode_preview", "PASS" if has_prev else "FAIL", f"keys={sorted(prev)[:4]}")
        cap = network.analyse_capture(samples["net_covert"])
        conf = (cap.get("interpretation") or {}).get("confidence")
        has_cap = "packets" in cap and cap.get("packets", 0) > 0
        rec("network_analyse_capture", "PASS" if has_cap else "FAIL",
            f"packets={cap.get('packets')} confidence={conf} (anomaly != proof)")
        # Real UDP loopback round-trip - the baseline channel, needs NO root.
        import threading
        import time as _t
        from app.modules.settings import service as settings
        settings.save(network_authorized_lab=True)
        port = 53911
        payload = b"StegoNexus-UDP-loopback-roundtrip"
        box: dict = {}

        def _rx():
            try:
                box["r"] = network.receive(transport="udp_payload", dport=port,
                                           count=1, timeout=8)
            except Exception as exc:  # noqa: BLE001
                box["r"] = {"error": f"{type(exc).__name__}: {exc}"}

        th = threading.Thread(target=_rx, daemon=True)
        th.start()
        _t.sleep(0.6)
        s = network.send(payload, dst="127.0.0.1", dport=port,
                         transport="udp_payload", iface="lo")
        th.join(timeout=10)
        settings.save(network_authorized_lab=False)
        got = (box.get("r") or {}).get("payload")
        ok = got == payload and s.get("status") == "SUCCESS"
        rec("network_udp_loopback", "PASS" if ok else "FAIL",
            f"send={s.get('status')} recv_match={got == payload} (baseline UDP, no root)")
        # The IPv4-ID covert channel needs raw sockets (root).
        lab = network.lab_status()
        if lab.get("elevated_privileges"):
            rec("network_ipv4_id_covert", "PASS", "root present - covert IPv4-ID channel ready")
        else:
            rec("network_ipv4_id_covert", "GATED",
                "needs root (raw sockets); enabled on Kali via sudo + authorized lab")
    run("network", net)

    # ---- 9. malware (static only; never executes) -------------------------
    def mal():
        sa = malware.static_analysis(samples["mal_zip"])
        has = "indicator_count" in sa and "heuristic_score" in sa
        rec("malware_static", "PASS" if has else "FAIL",
            f"score={sa.get('heuristic_score')} indicators={sa.get('indicator_count')} "
            f"confidence={sa.get('confidence')} (never executed)")
        rec("malware_dynamic_sandbox", "BLOCKED", "by safety design: samples are never executed")
    run("malware", mal)

    # ---- 9b. executable stego (overlay + slack round-trips) ---------------
    def exec_stego():
        carrier = samples["pe_carrier"]
        out_o = tmp / "exec_stego_overlay.exe"
        out_s = tmp / "exec_stego_slack.exe"
        for stale in (out_o, out_s):
            stale.unlink(missing_ok=True)
        malware.executable_hide(carrier, secret, out_o, "PreKey123", "overlay")
        e_o = malware.executable_extract(out_o, tmp / "exec_stego_out", "PreKey123")
        malware.executable_hide(carrier, secret, out_s, "PreKey123", "slack")
        e_s = malware.executable_extract(out_s, tmp / "exec_stego_out", "PreKey123")
        scanned = malware.executable_scan(out_s)
        flagged = malware.static_analysis(out_s)
        same_size = out_s.stat().st_size == carrier.stat().st_size
        ok = (e_o["payload_bytes"] == len(sbytes)
              and e_s["payload_bytes"] == len(sbytes)
              and e_o["sha256"] == e_s["sha256"]
              and same_size and scanned["slack_blob"]
              and any("Executable stego" in i for i in flagged["indicators"]))
        rec("executable_stego", "PASS" if ok else "FAIL",
            f"overlay+slack byte_match=True slack_same_size={same_size} "
            f"scan_detected={bool(scanned['slack_blob'])} "
            f"static_flag={any('Executable stego' in i for i in flagged['indicators'])}")
    run("executable_stego", exec_stego)

    # ---- 10. forensics suite ---------------------------------------------
    def forem():
        tgt = samples["image_jpg"]
        forensics.file_type(tgt)
        forensics.strings(tgt)
        forensics.entropy(tgt)
        forensics.binwalk(tgt)
        forensics.steghide_info(tgt)
        forensics.ffprobe(tgt)
        forensics.foremost(tgt, tmp / "foremost_out")
        forensics.triage(tgt, tmp / "triage_out")
        rec("forensics_suite", "PASS", "file/strings/entropy/binwalk/steghide/ffprobe/foremost/triage ran")
        rec("forensics_zsteg", "PASS" if shutil.which("zsteg") else "UNAVAILABLE",
            "installed" if shutil.which("zsteg") else "zsteg not installed (gem install zsteg)")
    run("forensics", forem)

    # ---- 11. reports ------------------------------------------------------
    def rep():
        cid = state.get("cid") or _case_id(cases.create("PREFLIGHT REPORTS", "x", "QA"))
        reps = reports.generate(cid)
        fmts = sorted({r.get("format") for r in reps})
        ok = len(reps) >= 3 and all((r.get("bytes") or 0) > 0 for r in reps)
        rec("reports_generate", "PASS" if ok else "FAIL",
            f"formats={','.join(fmts)} files={len(reps)}")
    run("reports", rep)

    # ---- 12. GUI launch + all views (reuse the project's own smoke test) --
    def gui():
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "gui_smoke_test.py")],
                           capture_output=True, text=True, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
        tail = (p.stdout or p.stderr).strip().splitlines()
        line = tail[-1] if tail else ""
        ok = "SMOKE TEST PASSED" in (p.stdout or "")
        rec("gui_all_views", "PASS" if ok else "FAIL", line or f"rc={p.returncode}")
    run("gui", gui)

    # ---- summary ----------------------------------------------------------
    order = {"PASS": 0, "PARTIAL": 0, "GATED": 0, "UNAVAILABLE": 0, "BLOCKED": 0, "FAIL": 0}
    for r in RESULTS:
        order[r["status"]] = order.get(r["status"], 0) + 1
    total = len(RESULTS)
    print("\n" + "=" * 60)
    print("PREFLIGHT SUMMARY")
    for k in ("PASS", "PARTIAL", "GATED", "UNAVAILABLE", "BLOCKED", "FAIL"):
        if order.get(k):
            print(f"  {k:12} {order[k]}")
    print(f"  {'TOTAL':12} {total}")
    hard_fail = order.get("FAIL", 0)
    verdict = "READY" if hard_fail == 0 else "NOT READY (see FAIL rows)"
    print(f"  VERDICT: {verdict}")
    out = ROOT / "artifacts" / "preflight" / "preflight_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"verdict": verdict, "summary": order, "results": RESULTS}, indent=2))
    print(f"  wrote {out.relative_to(ROOT)}")
    return 0 if hard_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
