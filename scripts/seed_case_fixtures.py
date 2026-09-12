#!/usr/bin/env python3
"""Create the three SYNTHETIC training cases (A/B/C) through the real services.

These are explicitly labelled ``TRAINING CASE - SYNTHETIC DATA`` and are NOT the course's
original Case 1/2/3. Every operation below is executed for real (hashes, evidence,
findings, logs and PDF/HTML/JSON reports are produced). Re-running is safe: each run
creates fresh, clearly-labelled cases.

Usage: QT_QPA_PLATFORM=offscreen python scripts/seed_case_fixtures.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LABEL = "TRAINING CASE - SYNTHETIC DATA"

from app.modules.audio import service as audio  # noqa: E402
from app.modules.cases import service as cases  # noqa: E402
from app.modules.evidence import service as evidence  # noqa: E402
from app.modules.findings import service as findings  # noqa: E402
from app.modules.hashing import service as hashing  # noqa: E402
from app.modules.image import service as image  # noqa: E402
from app.modules.malware import service as malware  # noqa: E402
from app.modules.metadata import service as metadata  # noqa: E402
from app.modules.network import service as network  # noqa: E402
from app.modules.reports import service as reports  # noqa: E402
from app.core.config import get_config  # noqa: E402
from scripts import seed_samples  # noqa: E402


def _tmp() -> Path:
    d = get_config().temp_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _new_case(letter: str, focus: str) -> dict:
    # Explicit unique TRN- numbers avoid same-second collisions and mark the case as a
    # synthetic training fixture.
    return cases.create(f"{LABEL} {letter}: {focus}",
                        number=f"TRN-{letter}-{int(time.time())}",
                        description=f"Synthetic educational fixture. {LABEL}. NOT an "
                                    f"original course case.", investigator="Training",
                        tags=f"synthetic,training,{letter}")


def case_a(samples) -> dict:
    case = _new_case("A", "Metadata + Image steganography")
    cid = case["id"]
    ev = evidence.import_file(cid, samples["image_png"], notes="synthetic noise carrier")
    meta = metadata.inject(samples["image_png"],
                           {"Comment": LABEL, "Author": "StegoNexus Training",
                            "Copyright": "Educational use"},
                           _tmp() / f"caseA_injected_{cid}.png",
                           case_id=cid, evidence_id=ev["id"])
    stego = _tmp() / f"caseA_stego_{cid}.png"
    hidden = image.native_embed(samples["image_png"], samples["text_secret"],
                                "caseA-key", stego, 3, case_id=cid, evidence_id=ev["id"])
    out = _tmp() / f"caseA_out_{cid}.txt"
    extracted = image.native_extract(stego, "caseA-key", out, case_id=cid)
    verified = hashing.verify(samples["text_secret"], out)["match"]
    evidence.register_artifact(cid, stego, notes="derived stego image")
    findings.create(cid, "Steganography", "Informational",
                    "Native LSB payload recovered and verified",
                    description=f"SHA-256 match={verified}; {LABEL}.")
    reports.generate(cid)
    return {"case": cid, "added_tags": meta["diff"]["counts"]["added"],
            "payload": hidden["payload_bytes"], "verified": verified}


def case_b(samples) -> dict:
    case = _new_case("B", "Audio LSB steganography")
    cid = case["id"]
    ev = evidence.import_file(cid, samples["audio_wav"], notes="synthetic sine carrier")
    stego = _tmp() / f"caseB_stego_{cid}.wav"
    hidden = audio.lsb_hide(samples["audio_wav"], samples["text_secret"], "caseB-key",
                            stego, case_id=cid, evidence_id=ev["id"])
    out = _tmp() / f"caseB_out_{cid}.txt"
    audio.lsb_extract(stego, "caseB-key", out, case_id=cid)
    verified = hashing.verify(samples["text_secret"], out)["match"]
    evidence.register_artifact(cid, stego, notes="derived stego audio")
    findings.create(cid, "Steganography", "Informational",
                    f"Audio LSB recovered (SNR {hidden['snr_db']} dB)",
                    description=f"SHA-256 match={verified}; {LABEL}.")
    reports.generate(cid)
    return {"case": cid, "snr_db": hidden["snr_db"], "verified": verified}


def case_c(samples) -> dict:
    case = _new_case("C", "Network PCAP + Malware static")
    cid = case["id"]
    evidence.import_file(cid, samples["net_covert"], notes="synthetic covert capture")
    interp = network.analyse_capture(samples["net_covert"], case_id=cid)
    mal = malware.static_analysis(samples["mal_txt"], case_id=cid)
    findings.create(cid, "Network", "Medium",
                    f"Covert-channel indicator ({interp['interpretation']['confidence']})",
                    description=f"Anomaly is an indicator, not proof. {LABEL}.")
    findings.create(cid, "Malware", "Informational",
                    f"Static analysis: {mal['indicator_count']} indicator(s)",
                    description=f"Defensive static only. {LABEL}.")
    reports.generate(cid)
    return {"case": cid,
            "net_confidence": interp["interpretation"]["confidence"],
            "mal_indicators": mal["indicator_count"]}


def main() -> int:
    samples = seed_samples.seed()
    for name, runner in (("A", case_a), ("B", case_b), ("C", case_c)):
        result = runner(samples)
        print(f"  Case {name}: {result}")
    print("Three SYNTHETIC training cases created (labelled; originals not claimed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
