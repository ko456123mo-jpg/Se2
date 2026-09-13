#!/usr/bin/env python3
"""Build the professional English documentation deliverable (DOCX, LTR).

Covers the three course requirements verbatim with real measured values from
the verified 36-step evidence run and real screenshots.
Usage: python scripts/build_documentation_en.py
Writes: /home/user/StegoNexus_Documentation_EN.docx
"""
from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "artifacts" / "evidence_report"
SHOTS = ROOT / "presentation" / "screenshots"
TMP = ROOT / "data" / "doc_imgs_en"
OUT = "/home/user/StegoNexus_Documentation_EN.docx"

DARK = RGBColor(0x0D, 0x3B, 0x66)
ACCENT = RGBColor(0x0B, 0x7A, 0x3D)
CYAN = RGBColor(0x0E, 0x74, 0x90)
GRAY = RGBColor(0x44, 0x55, 0x66)
AMBER = RGBColor(0x8A, 0x6D, 0x00)

STEPS = json.loads((EVID / "evidence_steps.json").read_text(encoding="utf-8"))
BY_FILE = {s["file"]: s for s in STEPS}
TMP.mkdir(parents=True, exist_ok=True)


def srun(run, size=11, bold=False, color=None, mono=False) -> None:
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    run.font.name = "Consolas" if mono else "Segoe UI"
    rPr = run._element.get_or_add_rPr()
    rF = rPr.find(qn("w:rFonts"))
    if rF is None:
        rF = OxmlElement("w:rFonts")
        rPr.append(rF)
    rF.set(qn("w:ascii"), "Consolas" if mono else "Segoe UI")
    rF.set(qn("w:hAnsi"), "Consolas" if mono else "Segoe UI")


def H(doc, text, size=16, color=DARK, before=14, after=4, align=WD_ALIGN_PARAGRAPH.LEFT):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    srun(p.add_run(text), size=size, bold=True, color=color)
    return p


def P(doc, text, size=11, bold=False, color=None, bullet=False, mono=False, italic=False):
    p = doc.add_paragraph(style="List Bullet" if bullet else None)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_after = Pt(3)
    for i, part in enumerate(text.split("**")):
        if not part:
            continue
        r = p.add_run(part)
        srun(r, size=size, bold=bold or (i % 2 == 1), color=color, mono=mono)
        r.font.italic = italic
    return p


def TBL(doc, headers, rows, widths=None, size=10) -> None:
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, htxt in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        srun(c.paragraphs[0].add_run(htxt), size=size, bold=True)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            srun(cells[i].paragraphs[0].add_run(str(val)), size=size)
    if widths:
        for i, w in enumerate(widths):
            for r in t.rows:
                r.cells[i].width = Inches(w)
    doc.add_paragraph()


def IMG(doc, filename, caption, folder=EVID, width=6.1) -> None:
    src = Path(folder) / filename
    if not src.exists():
        return
    im = Image.open(src).convert("RGB")
    new_w = int(width * 96)
    new_h = max(1, int(im.height * new_w / im.width))
    im = im.resize((new_w, new_h))
    dst = TMP / (Path(filename).stem + ".jpg")
    im.save(dst, "JPEG", quality=82)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(dst), width=Inches(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    srun(cap.add_run(caption), size=9.5, color=GRAY)


def REAL(doc, filename, note="Measured values for this step (from the verified evidence run)"):
    s = BY_FILE[filename]
    TBL(doc, ["Real inputs", "Value"], s["inputs"], widths=[2.6, 4.2], size=9.5)
    TBL(doc, ["Measured outputs", "Value"], s["outputs"], widths=[2.6, 4.2], size=9.5)
    P(doc, s["explain"], size=9.5, color=GRAY, italic=True)


# ------------------------------------------------------------------ document
doc = Document()
for sec in doc.sections:
    sec.left_margin = Inches(0.8)
    sec.right_margin = Inches(0.8)

# ============ cover
for _ in range(3):
    doc.add_paragraph()
H(doc, "Data Hiding & Digital Forensics Analysis - Course Project", size=14, color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER)
H(doc, "StegoNexus", size=34, align=WD_ALIGN_PARAGRAPH.CENTER)
H(doc, "An integrated platform for data hiding & extraction, malware analysis and digital forensics",
  size=15, color=CYAN, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()
H(doc, "Comprehensive Documentation", size=20, color=ACCENT, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()
doc.add_paragraph()
H(doc, "Developed by: Mohammed Moneer Al-absi", size=14, align=WD_ALIGN_PARAGRAPH.CENTER)
H(doc, "Supervisor: Osama Al-Shalali", size=13, color=CYAN, align=WD_ALIGN_PARAGRAPH.CENTER)
H(doc, "Academic Year 2026", size=12, color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_page_break()

# ============ TOC
H(doc, "Table of Contents", size=17)
for t in ["1. Introduction: problem, solution, objectives",
          "2. Tool overview & architecture",
          "3. Key terminology",
          "4. Requirement 1 - metadata viewing & injection tool",
          "5. Requirement 2 - hiding/extraction tools in Cases 1, 2, 3",
          "6. Requirement 3 - hiding/extraction tools per medium:",
          "      6.1 Images (2 techniques)   6.2 Audio (3 techniques)   6.3 Video (2 techniques)",
          "      6.4 Network (IPv4-ID covert channel)   6.5 Malware & viruses (2 techniques + detection)",
          "7. Security & ethics",
          "8. Testing & verification",
          "9. Requirements -> implementation -> verification map",
          "10. Installation & reproducing the results",
          "11. Conclusion"]:
    P(doc, t, size=11.5)
doc.add_page_break()

# ============ 1 intro
H(doc, "1. Introduction", size=17)
H(doc, "1.1 Problem", size=13)
P(doc, "Existing data-hiding tools used in the course are fragmented: each tool implements a single "
       "technique on a single platform (OpenPuff, DeepSound and CyberHide are Windows-only), with no link "
       "between hiding/extraction operations and forensic analysis, case management or reporting - and no "
       "way to prove that results are genuine rather than fabricated.", size=11)
H(doc, "1.2 Solution: StegoNexus", size=13)
P(doc, "A unified platform for **Kali Linux** built with **Python** and a **PySide6** GUI. It natively "
       "implements every steganography technique studied in the course, integrates the real external tools "
       "(ExifTool, Steghide, Binwalk, Foremost, FFmpeg, tshark, zsteg), and adds a complete investigation "
       "layer: cases, evidence with hashes, an audit trail and three-format reporting.", size=11)
H(doc, "1.3 Objectives", size=13)
for t in ["Cover 100% of the course requirements: metadata viewing & injection; hiding & extraction in "
          "text, images, audio, video, network and executables (malware/viruses).",
          "Implement more than one technique per medium (audio has 3; images, video and executables 2 each).",
          "Prove every result by measurement: SHA-256 match between recovered and original payload in every "
          "hide/extract round-trip.",
          "Full academic honesty: a status label on every capability, an audit record for every action, and "
          "explicitly declared limitations."]:
    P(doc, t, bullet=True, size=11)
H(doc, "1.4 Scope of use", size=13)
P(doc, "A defensive, educational tool for authorized laboratory use only: specimens are never executed, no "
       "offensive functionality exists, and network transmission is restricted to loopback / private ranges.", size=11)

# ============ 2 overview
H(doc, "2. Tool Overview", size=17)
H(doc, "2.1 Architecture", size=13)
TBL(doc, ["Layer", "Content"],
    [["Front-ends", "PySide6 GUI - 20 views (dark/light themes, async non-freezing operations) + interactive CLI; both are thin clients over the same services"],
     ["Services (17 modules)", "Each facade: input validation -> real work -> DB analysis row + audit log -> rich result"],
     ["Hiding engines (10)", "lsb_text - lsb_image - lsb_audio - phase_coding - spread_spectrum - container(EOF) - video_lsb - video_spread - pe_stego (overlay/slack)"],
     ["External tools", "Safe ToolExecutor (no shell=True): exiftool - steghide - binwalk - foremost - ffmpeg/ffprobe - tshark - file - strings - zsteg"],
     ["Defensive analysis", "PE/ELF/Office parsing - IOC - evasion catalogue - static malware analysis"],
     ["Storage", "SQLite (WAL): cases - evidence & hashes - findings - analyses - reports - logs; the dashboard is computed entirely from these tables"]],
    widths=[1.7, 5.1])
IMG(doc, "dashboard", "The dashboard - every figure computed from the live investigation database", folder=SHOTS)
H(doc, "2.2 Honesty policy (status vocabulary)", size=13)
TBL(doc, ["Status", "Meaning", "Examples"],
    [["IMPLEMENTED", "Native engine we wrote and tested", "10 hiding engines + forensic triage"],
     ["INTEGRATED", "Real external tool wired in", "ExifTool - Steghide - FFmpeg - Binwalk"],
     ["REFERENCE", "Course tool documented, never faked", "OpenPuff - CyberHide - DeepSound - Coagula"],
     ["EXTERNAL", "System tool the app can launch", "Wireshark - Audacity"],
     ["UNAVAILABLE", "Not installed - reported honestly", "Any missing tool shows this, never fake results"]],
    widths=[1.5, 2.7, 2.6])
H(doc, "2.3 Forensic frame", size=13)
P(doc, "Every investigation starts with a **Case**; **Evidence** files are imported and immediately hashed with "
       "4 algorithms (MD5/SHA-1/SHA-256/SHA-512) opening a chain of custody. Findings, the audit log and reports "
       "are all bound to the case. The original evidence is **never modified** - all operations run on working copies.", size=11)
IMG(doc, "s02.png", "Creating a real case and importing 6 evidence files with their hashes - from the verified run")

# ============ 3 terminology
H(doc, "3. Key Terminology", size=17)
TBL(doc, ["Term", "Definition"],
    [["Steganography / Steganalysis", "Hiding data inside digital media / the science of detecting and extracting it"],
     ["LSB - Least Significant Bit", "The last bit of a byte; flipping it changes the value by 1 only (imperceptible)"],
     ["Carrier / Cover - Payload", "The hosting medium (image/audio/video/text) - the hidden secret data"],
     ["SNR - Signal-to-Noise Ratio", "Distortion measure after embedding, in dB"],
     ["Entropy (Shannon)", "Randomness measure 0-8 bits/byte; high values indicate compression/encryption"],
     ["Phase Coding", "Hiding bits in the phase of the signal's FFT spectrum"],
     ["DSSS - Direct Sequence Spread Spectrum", "Spreading each bit across a pseudo-noise (PN) sequence"],
     ["Covert Channel", "A hidden channel through protocol fields (e.g. IPv4 Identification)"],
     ["EOF Container / PE Overlay", "Data appended after the file's logical end / after the PE sections"],
     ["Slack Space", "Unused padding between VirtualSize and SizeOfRawData in PE sections"],
     ["AES-256-GCM / PBKDF2", "Authenticated encryption / key derivation (200,000 iterations here)"],
     ["Hashing (MD5/SHA-1/SHA-256/SHA-512)", "Hashing: integrity and match verification"],
     ["Metadata (EXIF)", "Data about the file, not its content"],
     ["IOC - Indicators of Compromise", "URLs, addresses and suspicious strings extracted from specimens"],
     ["Static Analysis", "Inspecting bytes without ever executing the specimen"],
     ["Carving", "Extracting embedded files by signatures (binwalk/foremost)"],
     ["Timestomping / Masquerading", "Forged timestamps / disguised file type"]],
    widths=[2.9, 3.9], size=9.5)

# ============ 4 metadata
H(doc, "4. Requirement 1 - Metadata Viewing & Injection Tool", size=17)
H(doc, "4.1 Concept", size=13)
P(doc, "Metadata is data **about** the file, not its content: camera and lens, GPS coordinates, producing "
       "software, dates, comments. Forensically it is doubly valuable: it proves origin and timing (and may "
       "leak sensitive location data), and its injection itself is a lightweight hiding channel.", size=11)
H(doc, "4.2 Tool & techniques", size=13)
P(doc, "Tool: the real external **ExifTool** (status INTEGRATED) driven from the Metadata view, with four operations:", size=11)
TBL(doc, ["Operation", "What it does", "Safety guarantee"],
    [["Read", "List every tag of the file (group/tag/value)", "Read-only"],
     ["Inject", "Write tags (Comment/Artist/Copyright/...) into a new copy", "Original untouched - proven by before/after SHA-256"],
     ["Compare", "Tag-level before/after diff: added/removed/changed", "-"],
     ["Strip", "A clean copy without sensitive tags for safe sharing", "Removal happens on the copy"]],
    widths=[1.2, 3.6, 2.0])
H(doc, "4.3 Real results from the verified run", size=13)
IMG(doc, "s05.png", "Reading JPEG tags - 32 real tags via exiftool")
REAL(doc, "s05.png")
IMG(doc, "s06.png", "Injecting 3 tags into a copy - the before/after line proves the original is unchanged")
REAL(doc, "s06.png")
IMG(doc, "s07.png", "Metadata stripping - a clean copy for safe sharing")
REAL(doc, "s07.png")
P(doc, "Documented conclusion: injection happened on a copy only (the original's hash is identical before/after) - "
       "exactly the safety guarantee to state in the defense.", size=11, bold=True, color=ACCENT)

# ============ 5 cases
H(doc, "5. Requirement 2 - Hiding/Extraction Tools in Cases 1, 2, 3", size=17)
P(doc, "Cases are managed through the Cases/Evidence views: create a case -> import evidence (hashed) -> run "
       "hiding/extraction and analysis -> record findings -> generate a PDF/HTML/JSON report. The app ships "
       "four ready training cases (labelled TRAINING-SYNTHETIC) that mirror the three course-case patterns and "
       "prove every tool works inside a full case workflow:", size=11)
TBL(doc, ["Case", "Course pattern", "Tools & techniques used inside", "Measured verification"],
    [["Case 1 (pattern A)", "image + metadata",
      "Metadata Inject/Compare (ExifTool) + native Image LSB (Steghide also available)",
      "3 tags added - recovered payload SHA-256 match - original intact"],
     ["Case 2 (pattern B)", "audio",
      "Audio LSB (plus Phase Coding and DSSS available in the same view)",
      "SNR ~97dB - recovered payload match"],
     ["Case 3 (pattern C)", "network + malware",
      "Network PCAP Interpreter + Malware Static Analysis (defensive)",
      "High confidence on the capture (indicator, not proof) - analysis without execution"],
     ["Supporting Case (pattern D)", "executable (malware)",
      "Executable Stego: Overlay + Slack + Scan + static flag",
      "Size unchanged (slack) - recovered match - automatic flagging"]],
    widths=[1.35, 1.35, 2.85, 1.55], size=9.5)
P(doc, "The course's original cases: import them via Cases -> New Case -> Evidence -> Import and run the same "
       "views - the services are format-agnostic and require no code change.", size=11, color=AMBER)
IMG(doc, "s35.png", "The case report in three formats (PDF/HTML/JSON) generated from the case's own records")

# ============ 6 media
H(doc, "6. Requirement 3 - Hiding/Extraction Tools per Medium", size=17)
P(doc, "Every medium is implemented with more than one technique as the requirement allows. For each technique "
       "we present: the principle, the algorithm as actually implemented in the code, then the real measurements "
       "from the verified run (every round = hide -> extract -> SHA-256 comparison).", size=11)

H(doc, "6.1 Images - two techniques", size=14, color=CYAN)
H(doc, "Technique 1: native LSB (IMPLEMENTED engine)", size=12)
P(doc, "Principle: replacing the least significant bit of pixel channels - carrier and output must be lossless "
       "(PNG/BMP/TIFF) because JPEG re-compression destroys LSB data. The header is written at fixed slots and "
       "the body in an order derived from SHA-256(salt + key) with an XOR mask - a wrong key fails explicitly.", bullet=True, size=10.5)
IMG(doc, "s11.png", "Hiding inside PNG with the native LSB engine")
REAL(doc, "s11.png")
IMG(doc, "s12.png", "Extraction - byte-for-byte match with the original")
REAL(doc, "s12.png")
H(doc, "Technique 2: Steghide (INTEGRATED external tool)", size=12)
P(doc, "A real tool working in the transform domain (graph-theoretic algorithm with compression and password "
       "encryption); supports JPEG/BMP/WAV and does not support PNG (the unsupported-format failure is shown honestly).", bullet=True, size=10.5)
IMG(doc, "s13.png", "Hiding in JPEG via real steghide")
REAL(doc, "s13.png")

H(doc, "6.2 Audio - three techniques", size=14, color=CYAN)
H(doc, "Technique 1: LSB on PCM samples", size=12)
P(doc, "Replacing the LSB of 16-bit samples (one LSB step = 1/32768 of full scale - below the audible threshold). "
       "Other formats (MP3/FLAC) are first converted to PCM WAV with FFmpeg.", bullet=True, size=10.5)
IMG(doc, "s15.png", "Audio LSB hiding - measured SNR")
REAL(doc, "s15.png")
H(doc, "Technique 2: Phase Coding", size=12)
P(doc, "Split the signal into 1024-sample segments -> FFT -> force a phase difference of +pi/4 (bit 0) or -pi/4 "
       "(bit 1) on a high-energy bin -> rebuild with the original magnitudes (so the ear does not notice). "
       "Requires a carrier >= 15 s; stronger against simple analysis but fragile to re-encoding.", bullet=True, size=10.5)
IMG(doc, "s17.png", "Phase-coding hiding on a 16 s carrier")
REAL(doc, "s17.png")
H(doc, "Technique 3: Spread Spectrum (DSSS)", size=12)
P(doc, "Each bit is spread across 1024 slots with a +-1 pseudo-noise sequence derived from the key (measured "
       "processing gain in dB), and extraction is **blind**: the key alone suffices without the original carrier - "
       "the message energy sits below the noise floor.", bullet=True, size=10.5)
IMG(doc, "s19.png", "DSSS hiding on a 30 s carrier")
REAL(doc, "s19.png")
IMG(doc, "s20.png", "Blind extraction (key only) - full match")
REAL(doc, "s20.png")

H(doc, "6.3 Video - two techniques", size=14, color=CYAN)
H(doc, "Technique 1: LSB over FFV1 frames (lossless pipeline)", size=12)
P(doc, "ffprobe -> ffmpeg decodes frames to PNG -> per-frame LSB embedding (header in frame 0, body in key order) "
       "-> FFV1 re-encode inside MKV (zero loss) -> automatic verification by re-extraction. The app refuses mp4 "
       "output on purpose: any lossy re-encode destroys LSB bits.", bullet=True, size=10.5)
IMG(doc, "s21.png", "Video hiding via FFV1 LSB")
REAL(doc, "s21.png")
H(doc, "Technique 2: custom encrypted EOF container", size=12)
P(doc, "Layout: SNXEOF0001 marker + version + 16B salt + 12B nonce + file name + **AES-256-GCM** ciphertext "
       "(PBKDF2-SHA256, 200,000 iterations), appended after the video's end with a length trailer. Players read "
       "the video normally at 100%; Detect finds the container from the last 18 bytes without the key. Explicit "
       "statement: a custom academic container - **not OpenPuff and not compatible with it**.", bullet=True, size=10.5)
IMG(doc, "s23.png", "Hiding with the EOF container appended after the video")
REAL(doc, "s23.png")
IMG(doc, "s24.png", "Container detection (Detect) - from the file tail without the key")
REAL(doc, "s24.png")

H(doc, "6.4 Network - the IPv4 Identification covert channel", size=14, color=CYAN)
H(doc, "Principle & technique", size=12)
P(doc, "The IPv4 header's Identification field is set by the source and not standardized by routers -> it can "
       "carry **15 bits per packet** unchanged in transit. The payload is framed (SNXNET1 marker + chunk count + "
       "length + CRC-32) and split into 15-bit chunks; bit 15 carries parity over the chunk index to detect loss "
       "and reordering at reassembly.", bullet=True, size=10.5)
P(doc, "Three tools in the view: **Preview** (the IP-ID map with no traffic) - **Send/Receive** (a baseline, "
       "explicitly non-covert UDP channel for teaching contrast) - **the covert IPv4-ID channel** (requires root "
       "+ authorized-lab mode; proven PASS in preflight). The forensic side is a **PCAP interpreter** that states: "
       "an anomaly is an indicator, not proof.", bullet=True, size=10.5)
IMG(doc, "s26.png", "The IPv4-ID injection map for a real payload")
REAL(doc, "s26.png")
IMG(doc, "s28.png", "Real send & receive on loopback - payload matched")
REAL(doc, "s28.png")

H(doc, "6.5 Malware & viruses - static analysis + executable hiding (two techniques)", size=14, color=CYAN)
H(doc, "a) Defensive static analysis (never executed)", size=12)
P(doc, "Hashes -> file type -> strings -> entropy -> full PE inspection (known packer sections UPX/Themida, section "
       "entropy >= 7.2, entry point in the last executable section, implausible build timestamp) -> IOCs -> "
       "extension masquerading & RTLO -> timestomping -> obfuscation -> PyInstaller -> archives -> ELF -> Office. "
       "Score = 8 x indicator count (cap 100); confidence by correlation: 1 indicator = Low, < 3 = Medium, 3+ = High "
       "- a single indicator never proves anything.", bullet=True, size=10.5)
IMG(doc, "s29.png", "A full static analysis inside the view - specimen never executed")
REAL(doc, "s29.png")
H(doc, "b) Executable hiding - Technique 1: PE overlay", size=12)
P(doc, "Appending an AES-256-GCM container (SNXPEST001 marker, PBKDF2 200k) after the last PE section plus a "
       "length trailer - the classic dropper/installer pattern. Forensic footprint: the file size grows, so "
       "comparing the section-table end with the file size exposes it.", bullet=True, size=10.5)
IMG(doc, "s34.png", "Overlay technique: the size increase is visible and detected")
REAL(doc, "s34.png")
H(doc, "c) Executable hiding - Technique 2: section slack", size=12)
P(doc, "Writing the container into the section's padding (the gap between VirtualSize and SizeOfRawData) and "
       "zero-filling the rest - **the file size does not change at all**, so only a section-table analysis with "
       "byte-level padding inspection (the Scan hidden data button) reveals it; re-running static analysis then "
       "raises an Executable stego indicator automatically.", bullet=True, size=10.5)
IMG(doc, "s30.png", "Hiding 73 bytes in section padding - size unchanged (2048 -> 2048)")
REAL(doc, "s30.png")
IMG(doc, "s31.png", "Static detection: the .text section, blob offset and size")
REAL(doc, "s31.png")
IMG(doc, "s32.png", "Extraction - SHA-256 match with the original")
REAL(doc, "s32.png")
IMG(doc, "s33.png", "Static analysis flags the stego carrier automatically - a closed loop")
REAL(doc, "s33.png")
P(doc, "Training carrier: a synthetic PE with valid headers and a .text section carrying 768 bytes of padding and "
       "no code at all (entry point 0) - we teach the technique on a sample that cannot run (methodological honesty).", size=10.5, color=AMBER)

H(doc, "6.0 Text hiding - LSB with a key (bonus)", size=14, color=CYAN)
P(doc, "Eligible characters only (LSB flip stays a letter/digit) -> frame (SNX1 marker + key check + length + "
       "CRC-32) -> zlib compression -> XOR mask with a SHA-256-CTR stream -> bits written in a key-driven "
       "Fisher-Yates order. Detection: the measurable LSB bias via the Analyse button.", bullet=True, size=10.5)
IMG(doc, "s09.png", "Hiding a real message inside the cover text")
REAL(doc, "s09.png")

# ============ 7 security
doc.add_page_break()
H(doc, "7. Security & Ethics", size=17)
TBL(doc, ["Principle", "Implementation in the tool"],
    [["Read-only by default", "Original evidence is never modified; every operation runs on copies; before/after proof via SHA-256"],
     ["Malware: static only", "Specimens are never executed; no sandbox/detonation and no offensive code anywhere"],
     ["Network restricted", "Transmission disabled by default (authorized-lab switch + root for the covert channel); destinations limited to loopback/RFC1918"],
     ["Nothing fabricated", "Missing tool = UNAVAILABLE - an anomaly is an indicator, not proof - samples labelled TRAINING-SYNTHETIC"],
     ["Safe tool execution", "ToolExecutor uses argument lists (no shell=True) with per-tool timeouts - prevents command injection"]],
    widths=[1.9, 4.9])

# ============ 8 verification
H(doc, "8. Testing & Verification", size=17)
TBL(doc, ["Suite", "Result"],
    [["pytest (regression)", "34 passed - include hide/extract round-trips for every technique and training cases A-D"],
     ["preflight_check.py", "VERDICT: READY (21 PASS / 1 GATED / 1 BLOCKED by design) - under root: 22 PASS confirming the IPv4-ID covert channel"],
     ["gui_smoke_test", "20/20 views render without errors + an executable-stego evidence shot"],
     ["gui_button_test", "11/11 real button paths (including the executable Hide/Scan/Extract handlers)"],
     ["demo_end_to_end", "Every demo step executed for real, generating genuine reports"],
     ["Documented evidence run", "36 steps with measurements and screenshots (this document is drawn from it) - all 10 hide/extract rounds matched by SHA-256"]],
    widths=[2.3, 4.5])

# ============ 9 mapping
H(doc, "9. Requirements -> Implementation -> Verification Map", size=17)
TBL(doc, ["Course requirement", "View", "Technique / tool", "Verification"],
    [["Metadata viewing", "Metadata -> Read", "ExifTool", "32 tags really read (s05)"],
     ["Metadata injection", "Metadata -> Inject/Strip/Compare", "ExifTool on a copy", "3 tags + unchanged=True (s06/s07)"],
     ["Case 1 (image)", "Cases + Image", "Native LSB + Steghide", "Recovered SHA-256 match (s11-s14)"],
     ["Case 2 (audio)", "Audio", "LSB + Phase + DSSS", "SNR ~97dB + match (s15-s20)"],
     ["Case 3 (network/malware)", "Network + Malware", "IPv4-ID + PCAP + Static", "SUCCESS/SUCCESS + High (s26-s29)"],
     ["Video hiding", "Video", "FFV1 LSB + EOF container", "Match + detection (s21-s25)"],
     ["Malware / viruses", "Malware", "Overlay + Slack + static detection", "Constant size + match + flag (s29-s34)"],
     ["Documentation", "Reports + Logs", "PDF/HTML/JSON + audit trail", "3 formats from the records (s35/s36)"]],
    widths=[1.7, 1.7, 1.9, 1.5], size=9.5)

# ============ 10 install
H(doc, "10. Installation & Reproducing the Results", size=17)
P(doc, "On Kali/Debian:", size=11, bold=True)
for c in ["sudo ./scripts/install_kali.sh    # external tools + Qt + .venv + Python deps",
          "./scripts/preflight.sh             # full check: VERDICT: READY",
          "./scripts/run.sh                   # the GUI",
          "sudo ./scripts/run.sh              # with the covert IPv4-ID channel (raw sockets)"]:
    P(doc, c, size=10, mono=True)
P(doc, "Reproducing the documented run behind this document:", size=11, bold=True)
for c in ["QT_QPA_PLATFORM=offscreen python scripts/capture_evidence_report.py",
          "python scripts/build_evidence_report_ar.py     # the illustrated HTML report",
          "python -m pytest -q                            # 34 tests"]:
    P(doc, c, size=10, mono=True)

# ============ 11 conclusion
H(doc, "11. Conclusion", size=17)
P(doc, "StegoNexus fully covers the course requirements: a metadata viewing & injection tool; working "
       "hiding/extraction tools inside complete case workflows; and per-medium hiding/extraction tools "
       "(images with 2 techniques, audio with 3, video with 2, network with a covert channel plus an interpreter, "
       "and malware/viruses with overlay & slack techniques plus a complete static detection loop) - all "
       "documented with real measurements reproducible by a single command. The core academic value: **a platform "
       "that always tells the truth about what it did, with which tool and which hash - and clearly states what "
       "it cannot do.**", size=11.5)
doc.add_paragraph()
P(doc, "Developed by: Mohammed Moneer Al-absi - Supervisor: Osama Al-Shalali - 2026", size=11, color=GRAY)

doc.save(OUT)
print("saved", OUT)
