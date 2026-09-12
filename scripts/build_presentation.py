#!/usr/bin/env python3
"""Build StegoNexus_Presentation.pptx from the REAL application screenshots.

Run the GUI smoke test first so ``presentation/screenshots`` is fresh:
    QT_QPA_PLATFORM=offscreen python scripts/gui_smoke_test.py
then:
    python scripts/build_presentation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

SHOTS = ROOT / "presentation" / "screenshots"
LOGO = ROOT / "resources" / "branding" / "stegonexus-logo-dark.png"
OUT = ROOT / "StegoNexus_Presentation.pptx"

DARK_BG = RGBColor(0x0B, 0x12, 0x20)
ACCENT = RGBColor(0x22, 0xD3, 0xEE)
TEXT = RGBColor(0xE6, 0xF0, 0xFB)
MUTED = RGBColor(0x8F, 0xA6, 0xC2)

SLIDES = [
    ("dashboard.png", "3. Dashboard - every figure computed from the live database"),
    ("metadata.png", "4. Metadata: read / inject / strip on copies (ExifTool)"),
    ("forensics.png", "5. Forensics: file / strings / entropy / binwalk / foremost / triage"),
    ("text.png", "6. Text steganography: native LSB + Key"),
    ("image.png", "6. Image: native LSB + Steghide; CyberHide is REFERENCE"),
    ("audio.png", "7. Audio: LSB / phase / spread spectrum with measured SNR"),
    ("video.png", "8. Video: FFV1 LSB + custom academic EOF container (AES-256-GCM)"),
    ("network.png", "9. Network lab: authorized-only; anomaly is an indicator not proof"),
    ("malware.png", "10. Malware: defensive static analysis only (never executed)"),
    ("hashing.png", "11. Hashing & integrity: MD5..SHA-512 with MATCH / MISMATCH"),
    ("cases.png", "11. Cases: status workflow + synthetic training fixtures"),
    ("reports.png", "11. Reports: branded PDF / HTML / JSON from stored records"),
    ("toolhealth.png", "Tool Health - measured matrix; missing tools are UNAVAILABLE"),
    ("externaltools.png", "External Tools Matrix - REFERENCE / EXTERNAL, never faked"),
    ("dashboard-light.png", "Light theme - the same UI in both themes"),
]


def _bg(slide) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = DARK_BG


def _title(slide, text: str, size: int = 30) -> None:
    box = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.9))
    frame = box.text_frame
    frame.word_wrap = True
    p = frame.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = True
    run.font.color.rgb = TEXT


def main() -> int:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # Title slide -------------------------------------------------------------
    slide = prs.slides.add_slide(blank)
    _bg(slide)
    if LOGO.exists():
        slide.shapes.add_picture(str(LOGO), Inches(3.6), Inches(1.6), width=Inches(6.1))
    sub = slide.shapes.add_textbox(Inches(1.5), Inches(3.4), Inches(10.3), Inches(1.4))
    tf = sub.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "Unified Hiding, Extraction & Forensics Framework"
    r.font.size = Pt(26)
    r.font.color.rgb = ACCENT
    p2 = tf.add_paragraph()
    r2 = p2.add_run()
    r2.text = ("Hide it. Extract it. Analyze it. Verify it. "
               "Investigate it. Document it. Report it.")
    r2.font.size = Pt(16)
    r2.font.color.rgb = MUTED

    # Agenda ------------------------------------------------------------------
    slide = prs.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "Agenda")
    body = slide.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(11.7), Inches(5.4))
    btf = body.text_frame
    btf.word_wrap = True
    for line in ["1. Live dashboard computed from the investigation database",
                 "2. Measured tool health - nothing is faked",
                 "3. Text / image / audio / video steganography (native + integrated)",
                 "4. Custom academic video EOF container - deliberately NOT OpenPuff",
                 "5. Authorized network lab - anomaly is an indicator, not proof",
                 "6. Defensive malware analysis",
                 "7. Forensics, hashing, metadata and branded reporting",
                 "8. Honest limitations and what is REFERENCE / UNAVAILABLE"]:
        p = btf.add_paragraph()
        r = p.add_run()
        r.text = line
        r.font.size = Pt(18)
        r.font.color.rgb = TEXT
        p.space_after = Pt(8)

    # Problem & architecture text slides -------------------------------------
    slide = prs.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "1. Problem & Goal")
    body = slide.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(11.7), Inches(5.4))
    btf = body.text_frame
    btf.word_wrap = True
    for line in [
            "Problem: steganography tools are fragmented - hiding, extraction, forensics,"
            " case management and reporting live in separate, often Windows-only tools.",
            "Goal: one honest, Kali-native workbench that hides, extracts, analyzes,"
            " verifies, investigates, documents and reports - with measured statuses.",
            "Non-goals: no fake results, no offensive malware, no unauthorized network use."]:
        p = btf.add_paragraph()
        r = p.add_run()
        r.text = "• " + line
        r.font.size = Pt(17)
        r.font.color.rgb = TEXT
        p.space_after = Pt(10)

    slide = prs.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "2. Architecture")
    body = slide.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(11.7), Inches(5.4))
    btf = body.text_frame
    btf.word_wrap = True
    for line in [
            "PySide6 GUI + CLI front-ends over shared Python service facades.",
            "SQLite (WAL) persistence: cases, evidence hashes, findings, analyses, logs.",
            "Native engines (LSB/phase/spread/container) + ToolExecutor-wrapped externals.",
            "Async QThreadPool workers keep the UI responsive; offscreen smoke-tested.",
            "Honesty layer: fixed status vocabulary on every operation and report."]:
        p = btf.add_paragraph()
        r = p.add_run()
        r.text = "• " + line
        r.font.size = Pt(17)
        r.font.color.rgb = TEXT
        p.space_after = Pt(8)

        # Screenshot slides -------------------------------------------------------
    for filename, caption in SLIDES:
        path = SHOTS / filename
        if not path.exists():
            print(f"  (skipping missing screenshot: {filename})")
            continue
        slide = prs.slides.add_slide(blank)
        _bg(slide)
        _title(slide, caption, size=22)
        slide.shapes.add_picture(str(path), Inches(1.1), Inches(1.2),
                                 width=Inches(11.1))

    # Honesty slide -----------------------------------------------------------
    slide = prs.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "Honesty Policy & Limitations")
    body = slide.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(11.7), Inches(5.4))
    btf = body.text_frame
    btf.word_wrap = True
    for line in [
            "Every capability carries a status label: IMPLEMENTED, INTEGRATED, REFERENCE,"
            " EXTERNAL, OPTIONAL or UNAVAILABLE.",
            "zsteg is not installed (Ruby gem) - reported UNAVAILABLE, never fabricated.",
            "OpenPuff / CyberHide / DeepSound / CoagulaLight are REFERENCE applications.",
            "The custom video EOF container is NOT OpenPuff-compatible - by design.",
            "Network transmission needs the authorized-lab switch and root privileges.",
            "Malware analysis is static and defensive; specimens are never executed.",
            "An anomaly in a header field is an indicator - never proof of hidden data.",
            "Case 1/2/3 practical material is required to reproduce those exact cases."]:
        p = btf.add_paragraph()
        r = p.add_run()
        r.text = "• " + line
        r.font.size = Pt(16)
        r.font.color.rgb = TEXT
        p.space_after = Pt(6)

    count = len(prs.slides._sldIdLst)
    prs.save(str(OUT))
    print(f"Saved {OUT} with {count} slides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
