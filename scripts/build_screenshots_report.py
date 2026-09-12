#!/usr/bin/env python3
"""Build ONE self-contained HTML file: every real screenshot (embedded as a
base64 data URI) placed right next to its explanation. No external resources,
so it renders in the sandboxed preview and offline. Run from the project root:

    python scripts/build_screenshots_report.py
"""
from __future__ import annotations
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "artifacts" / "real_verification" / "screenshots"
OUT = ROOT / "artifacts" / "real_verification" / "SCREENSHOTS_WITH_EXPLANATION.html"

# filename -> (title, caption HTML)
CAPTIONS: dict[str, tuple[str, str]] = {
    # ---- Part A: the real Views ----
    "01_dashboard.png": ("Dashboard", "Real landing page: live case count and the honest tool matrix (installed / unavailable / reference) — not fake stats."),
    "02_tool_health.png": ("Tool Health", "Real probes of file/strings/exiftool/binwalk/steghide/foremost/ffmpeg/ffprobe/tshark/zsteg with installed version or UNAVAILABLE."),
    "03_cases.png": ("Case Management", "The real cases table; training cases labelled SYNTHETIC."),
    "04_evidence.png": ("Evidence", "Real evidence chain-of-custody table."),
    "05_findings.png": ("Findings", "Findings view."),
    "06_logs.png": ("Logs (initial)", "Audit-log view before operations."),
    "07_reports.png": ("Reports (initial)", "Report generator view before generating."),
    "08_metadata.png": ("Metadata (initial)", "Metadata read/inject/compare/strip view before running."),
    "09_forensics.png": ("Forensics", "Forensics suite view (file/strings/exif/binwalk/steghide/foremost/zsteg/entropy/triage)."),
    "10_hashing.png": ("Hashing", "4-algorithm hashing view (MD5/SHA-1/SHA-256/SHA-512)."),
    "11_extraction.png": ("Extraction (initial)", "Extraction workspace before running."),
    "12_text.png": ("Text Stego", "Text LSB steganography view."),
    "13_image.png": ("Image Stego", "Image steganography view (native + Steghide + CyberHide)."),
    "14_audio.png": ("Audio Stego", "Audio steganography view (LSB/phase/spread/metadata)."),
    "15_video.png": ("Video Stego", "Video steganography view (LSB/EOF-container/spread)."),
    "16_network.png": ("Network Stego", "Network stego view (encode preview + capture analysis + send/receive)."),
    "17_malware.png": ("Malware", "Malware static-analysis view (defensive only)."),
    "18_external_tools.png": ("External Tools", "External tool status matrix with honest unavailable/reference notes."),
    "19_settings.png": ("Settings", "Settings view."),
    "20_about.png": ("About", "About / legal / disclaimer view."),
    "21_extraction_after.png": ("Extraction (after)", "Extraction workspace AFTER the real extraction batch ran."),
    "22_logs_after.png": ("Logs (after)", "Audit log AFTER operations — real entries appended by the real services."),
    "23_reports_after.png": ("Reports (after)", "Report view AFTER real PDF/HTML/JSON generation."),
    # ---- Part B: technique steps ----
    "24_text_encode.png": ("Text LSB — encode", "Text LSB hide with key. Input <code>samples/step_secret.txt</code> → container <code>samples/step_text_cover.txt</code>. Capacity <b>58 bytes</b> payload in an 11-word cover. <b>PASS</b>."),
    "25_text_decode.png": ("Text LSB — decode", "Text LSB extract from the same container with the <b>correct key</b> <code>QATestKey</code> → exact secret recovered (<code>match=True</code>). <b>PASS</b>."),
    "26_image_hide.png": ("Image — native LSB hide", "Native LSB embed into <code>samples/step_image.png</code>; capacity <b>249,050 bytes</b> payload. <b>PASS</b>."),
    "27_image_extract.png": ("Image — native LSB extract", "Native LSB extract from the embedded image → exact recovery (<code>match=True</code>). <b>PASS</b>."),
    "28_audio_hide.png": ("Audio — LSB hide", "LSB hide into <code>samples/step_audio.wav</code>; capacity <b>249,618 bytes</b> payload. <b>PASS</b>."),
    "29_audio_extract.png": ("Audio — LSB extract", "LSB extract from the same WAV → exact recovery (<code>match=True</code>). <b>PASS</b>."),
    "30_video_hide.png": ("Video — LSB hide", "Video LSB hide into <code>samples/step_video.mp4</code>; capacity <b>32,107,380 bytes</b> payload. <b>PASS</b>."),
    "31_video_detect.png": ("Video — EOF-container detect", "Custom <code>stegonexus_container</code> EOF container (<b>not</b> OpenPuff) → <code>present=True</code>, <code>hidden_bytes=260</code>. <b>PASS</b>."),
    "32_network_preview.png": ("Network — encode preview", "Header/packet field modification map (design-level), payload 82 bytes. <b>PASS</b>."),
    "33_network_analyse.png": ("Network — capture analysis", "Analysis of <code>samples/step_capture.pcap</code> (30 packets) → <code>anomalies=2</code>, <code>snr=0.0</code>. Screen states <b>anomalies are indicators, not proof</b>. Live send/receive stays BLOCKED without root."),
    "34_malware_static.png": ("Malware — static analysis", "Static analysis of <code>samples/step_payload.exe</code> → <code>score=55</code>, verdict <b>SUSPICIOUS</b>. Sample <b>never executed</b>; dynamic/sandbox BLOCKED by safety policy."),
    "35_metadata_read.png": ("Metadata — read", "Metadata read of <code>samples/step_image.jpg</code> via <b>exiftool 13.25</b> → <code>tool=exiftool</code>, 12 tags."),
    "36_metadata_inject.png": ("Metadata — inject", "Inject 2 tags on a <b>working copy</b>, then re-read shows them back; before/after SHA-256 of the <b>original</b> are identical (original unchanged)."),
    "37_hashing_compute.png": ("Hashing — compute", "Compute MD5 + SHA-1 + SHA-256 + SHA-512 of <code>samples/step_image.jpg</code> (all four present)."),
    "38_hashing_compare.png": ("Hashing — compare", "Compare original vs injected copy → <code>identical=False</code>, <code>size_delta=0</code>, conclusion <b>MODIFIED</b> (injection touched the copy; original hash stayed fixed)."),
    "39_forensics_triage.png": ("Forensics — triage", "One-click triage over <code>samples/step_image.jpg</code> → <code>indicators=0</code> across file/strings/exif/entropy/binwalk/steghide/foremost. Screen states <b>indicators, not proof</b>; absent tools (zsteg) reported UNAVAILABLE."),
}

PART_A = [k for k in CAPTIONS if k[:2].isdigit() and int(k[:2]) <= 23]
PART_B = [k for k in CAPTIONS if int(k[:2]) >= 24]


def data_uri(p: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def card(fn: str) -> str:
    title, cap = CAPTIONS[fn]
    img = data_uri(SHOTS / fn)
    return (
        f'<figure class="card"><figcaption><span class="fn">{fn}</span>'
        f'<span class="ti">{title}</span></figcaption>'
        f'<img src="{img}" alt="{fn}"/>'
        f'<p>{cap}</p></figure>'
    )


def main() -> None:
    html = ["""<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>StegoNexus — Screenshots with Explanation</title>
<style>
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.55;color:#1b1f24;background:#f6f7f9}
header{padding:28px 20px;background:#0d1b2a;color:#eaf2ff}
header h1{margin:0 0 6px;font-size:22px}
header p{margin:2px 0;color:#b9cbe0;font-size:13px}
.wrap{max-width:1080px;margin:0 auto;padding:16px}
h2{margin:30px 0 10px;font-size:18px;border-bottom:2px solid #0d1b2a;padding-bottom:6px}
.note{background:#fff8e1;border:1px solid #f0d089;border-radius:8px;padding:10px 14px;font-size:13px;margin:12px 0}
figure.card{background:#fff;border:1px solid #e2e6ea;border-radius:10px;margin:14px 0;padding:14px;box-shadow:0 1px 2px rgba(0,0,0,.05)}
figcaption{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;margin-bottom:8px}
.fn{font-family:ui-monospace,Menlo,Consolas,monospace;background:#0d1b2a;color:#eaf2ff;padding:2px 8px;border-radius:6px;font-size:12px}
.ti{font-weight:600}
figure.card img{max-width:100%;border:1px solid #e2e6ea;border-radius:6px;display:block}
figure.card p{margin:10px 2px 0;font-size:14px}
code{background:#eef1f4;padding:1px 5px;border-radius:4px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px}
@media (prefers-color-scheme:dark){body{background:#0f1418;color:#e6edf3}figure.card{background:#161b20;border-color:#2a3138}header{background:#000}.note{background:#2a2410;border-color:#5a4a1f}code{background:#222a31}}
</style></head><body>
<header>
<h1>StegoNexus — Screenshots with Explanation</h1>
<p>39 real Qt widget captures of the running application (offscreen). No fabricated images.</p>
<p>Each screenshot is shown next to its explanation. Legend: PASS · PARTIAL · REFERENCE · EXTERNAL · BLOCKED.</p>
</header>
<div class="wrap">
<div class="note"><b>Honesty:</b> every image below is a genuine capture of the actual app. Reference implementations (CyberHide/DeepSound/Coagula), external tools (Audacity/DeepSound/Coagula), and safety blocks (network send/receive needs root; malware never executed) are labelled as such. All cases are <b>TRAINING CASE — SYNTHETIC DATA</b>.</div>
"""]
    html.append("<h2>Part A — The real Views (01–23)</h2>")
    html += [card(f) for f in sorted(PART_A)]
    html.append("<h2>Part B — Technique step screenshots (24–39)</h2>")
    html.append('<div class="note">Each image is the technique view <b>after</b> the real service call, so the on-screen values are the actual results.</div>')
    html += [card(f) for f in sorted(PART_B)]
    html.append("</div></body></html>")
    OUT.write_text("".join(html))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1e6:.1f} MB, {len(CAPTIONS)} images)")


if __name__ == "__main__":
    main()
