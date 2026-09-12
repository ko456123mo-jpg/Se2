#!/usr/bin/env python3
"""StegoNexus end-to-end demonstration (project rule 72).

Runs the primary workflow headlessly and prints an honest, step-by-step audit:

    Create Case -> Import Image -> SHA-256 -> Metadata -> Forensics
    -> Hide secret -> New hash -> Extract -> Hash extracted -> Finding -> Report

It also demonstrates one workflow each for text, audio, video, network and
malware analysis when the corresponding tool is available.  Nothing is faked:
every line printed comes from a real execution.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PIL import Image

from app.core.config import get_config
from app.modules.cases import service as cases
from app.modules.evidence import service as evidence
from app.modules.findings import service as findings
from app.modules.forensics import service as forensics
from app.modules.hashing import service as hashing
from app.modules.image import service as image
from app.modules.malware import service as malware
from app.modules.metadata import service as metadata
from app.modules.network import service as network
from app.modules.reports import service as reports
from app.modules.text import service as text
from app.modules.audio import service as audio
from app.modules.video import service as video

BANNER = "StegoNexus - end-to-end demonstration"


def section(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(0, 72 - len(title)))


def _make_samples(samples_dir: Path) -> dict:
    samples_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    cover = samples_dir / "demo_carrier.png"
    if not cover.exists():
        Image.fromarray(rng.integers(0, 255, (600, 800, 3), dtype=np.uint8),
                        "RGB").save(cover)
    secret = samples_dir / "demo_secret.txt"
    secret.write_text("CLASSIFIED: project Nexus briefing at 09:00. Bring the "
                      "integrity manifest.\n", encoding="utf-8")
    return {"cover": cover, "secret": secret}


def main() -> int:
    started = time.perf_counter()
    cfg = get_config()
    print(BANNER)
    print(f"workspace: {cfg.root}")
    samples = _make_samples(cfg.samples_dir)

    section("1. Create case")
    case = cases.create("Demonstration case", "End-to-end workflow walkthrough",
                        investigator="Demo Investigator", tags="demo,graduation")
    print(f"case #{case['id']} {case['number']} '{case['title']}'")

    section("2. Import image evidence")
    ev = evidence.import_file(case["id"], samples["cover"], notes="random-noise cover")
    print(f"evidence #{ev['id']} {ev['name']} sha256={ev['sha256'][:20]}... "
          f"({ev['size']} bytes)")

    section("3. Hash (SHA-256 primary)")
    h = hashing.hash_file(samples["cover"], case_id=case["id"], evidence_id=ev["id"])
    for name in ("md5", "sha1", "sha256", "sha512"):
        print(f"  {name:<7} {h.hashes[name][:32]}...")

    section("4. Metadata analysis (ExifTool)")
    meta = metadata.read(samples["cover"], case_id=case["id"], evidence_id=ev["id"])
    print(f"source={meta.source} tags={meta.count}")
    for row in meta.entries[:6]:
        print("  ", row.as_row())

    section("5. Forensic triage")
    for kind in ("file_type", "entropy", "binwalk"):
        func = getattr(forensics, kind)
        res = func(samples["cover"], case_id=case["id"], evidence_id=ev["id"])
        print(f"  {kind:<10} [{res['status']}] {res['summary'][:80]}")

    section("6. Hide secret in image (native LSB, verified)")
    stego = cfg.data_dir / "tmp" / "demo_stego.png"
    hide = image.native_embed(samples["cover"], samples["secret"], "demo-key-1", stego,
                              case_id=case["id"], evidence_id=ev["id"])
    print(f"status={hide['status']} verified={hide['verified']} "
          f"util={hide['utilisation']:.4%} stego={stego.name}")

    section("7. Extract secret and verify")
    recovered = cfg.data_dir / "tmp" / "demo_recovered.txt"
    ext = image.native_extract(stego, "demo-key-1", recovered, case_id=case["id"])
    print(f"extracted {ext['payload_bytes']} bytes -> {recovered.name}")
    ver = hashing.verify(samples["secret"], recovered)
    print(f"integrity vs original: match={ver['match']}")
    evidence.register_artifact(case["id"], stego, "derived", "stego image", "demo")
    evidence.register_artifact(case["id"], recovered, "extracted", "recovered secret", "demo")

    section("8. Create finding")
    finding = findings.create(case["id"], "Steganography", "Informational",
                              "Recovered hidden payload during demonstration",
                              description="LSB payload recovered and hash-verified.",
                              indicator="native LSB round-trip", evidence_id=ev["id"],
                              confidence="High")
    print(f"finding #{finding['id']} [{finding['severity']}] {finding['title']}")

    section("9. Text LSB + key")
    cover_text = Path(samples["cover"]).read_bytes()[:0] or None
    text_cover = ("In the quiet of the laboratory the instruments hummed, and the "
                  "researchers recorded every reading twice. " * 30)
    t_hide = text.hide(text_cover, "MEET AT GRID 44N", "text-key", None, case_id=case["id"])
    t_ext = text.extract(t_hide["stego_text"], "text-key", None, case_id=case["id"])
    print(f"hidden={t_hide['stats']['secret_bytes']}B extracted='{t_ext['message']}' "
          f"match={t_ext['message'] == 'MEET AT GRID 44N'}")

    section("10. Audio LSB (verified)")
    sr = 44100
    t = np.arange(sr * 4) / sr
    wav = cfg.data_dir / "tmp" / "demo_carrier.wav"
    signal = (0.3 * np.sin(2 * np.pi * 440 * t) + 0.15 * np.sin(2 * np.pi * 990 * t)) * 30000
    import wave as _wave

    with _wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(signal.astype("<i2").tobytes())
    a_hide = audio.lsb_hide(wav, samples["secret"], "audio-key",
                            cfg.data_dir / "tmp" / "demo_stego.wav",
                            case_id=case["id"])
    print(f"audio LSB verified={a_hide['verified']} SNR={a_hide['snr_db']}dB")

    section("11. Video container EOF hiding (custom academic)")
    mkv = cfg.data_dir / "tmp" / "demo_carrier.mkv"
    if not mkv.exists():
        from app.services.tool_executor import executor

        if executor.is_available("ffmpeg"):
            executor.run("ffmpeg", ["-y", "-v", "error", "-f", "lavfi",
                                    "-i", "testsrc=duration=2:size=320x240:rate=10",
                                    "-pix_fmt", "rgb24", "-c:v", "ffv1", str(mkv)],
                         timeout=120)
    if mkv.exists():
        v_hide = video.container_hide(mkv, samples["secret"], "video-key",
                                      cfg.data_dir / "tmp" / "demo_stego.mkv",
                                      case_id=case["id"])
        print(f"container hide payload={v_hide['payload_bytes']}B blob={v_hide['blob_bytes']}B "
              f"class={v_hide['classification'][:40]}")

    section("12. Network channel (encode preview + interpreter)")
    preview = network.encode_preview(b"COVERT LAB DEMO MESSAGE")
    print(f"packets={preview['packets']} bits={preview['bits']}")
    from app.network import encoder as _enc
    from app.network import interpreter as _int

    pkts = [{"index": i, "src": "127.0.0.1", "dst": "127.0.0.1", "proto": "UDP",
             "length": 42, "sport": 53001, "dport": 53000, "ip_id": v, "ttl": 64,
             "payload_len": 0, "payload_preview": ""}
            for i, v in enumerate(preview["ip_ids"])]
    analysis = _int.interpret(pkts)
    print(f"network interpretation confidence={analysis.confidence}: "
          f"{analysis.assessment[:60]}")

    section("13. Malware static analysis (safe)")
    mal = malware.static_analysis(samples["secret"], case_id=case["id"],
                                  evidence_id=ev["id"])
    print(f"indicators={mal['indicator_count']} score={mal['heuristic_score']}/100 "
          f"pe={mal['pe']['is_pe']}")

    section("14. Generate report")
    out = reports.generate(case["id"], formats=("pdf", "html", "json"), theme="light")
    for record in out:
        print(f"  {record['format']:<5} {Path(record['path']).name} "
              f"({record['bytes']} bytes) sha256={record['sha256'][:16]}...")

    section("RESULT")
    print(f"demo completed in {time.perf_counter() - started:,.1f}s. "
          f"All steps above were executed for real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
