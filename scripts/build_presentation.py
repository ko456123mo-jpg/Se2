#!/usr/bin/env python3
"""StegoNexus — professional presentation builder (bilingual AR/EN, 16:9).

Design system: dark navy canvas, cyan/green accents, RTL Arabic typography,
drawn diagrams (architecture, PE layout, IPv4 header), real screenshots and
real measured numbers from the verified evidence run.

Usage: python scripts/build_presentation.py
Writes: StegoNexus_Presentation.pptx
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "presentation" / "screenshots"
EVID = ROOT / "artifacts" / "evidence_report"
OUT = ROOT / "StegoNexus_Presentation.pptx"

# ------------------------------------------------------------------ palette
BG = RGBColor(0x0A, 0x11, 0x20)
PANEL = RGBColor(0x11, 0x1C, 0x30)
PANEL2 = RGBColor(0x16, 0x23, 0x3B)
BORDER = RGBColor(0x2A, 0x3B, 0x59)
CYAN = RGBColor(0x22, 0xD3, 0xEE)
GREEN = RGBColor(0x34, 0xD3, 0x99)
AMBER = RGBColor(0xFB, 0xBF, 0x24)
RED = RGBColor(0xF8, 0x71, 0x71)
VIOLET = RGBColor(0xA7, 0x8B, 0xFA)
TEXT = RGBColor(0xEA, 0xF2, 0xFC)
MUTED = RGBColor(0x93, 0xA7, 0xC4)
INK = RGBColor(0x07, 0x0C, 0x16)

W, Hh = Inches(13.333), Inches(7.5)

prs = Presentation()
prs.slide_width = W
prs.slide_height = Hh
BLANK = prs.slide_layouts[6]

SLIDE_NO = {"n": 0}


# ------------------------------------------------------------------ helpers
def new_slide() -> "Slide":
    s = prs.slides.add_slide(BLANK)
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = BG
    SLIDE_NO["n"] += 1
    return s


def _set_ar(p, rtl=True):
    if rtl:
        pPr = p._p.get_or_add_pPr()
        pPr.set("rtl", "1")


def _style_run(run, size, bold, color, mono=False):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    f.name = "Consolas" if mono else "Segoe UI"
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:cs", "a:latin"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", "Consolas" if mono else "Segoe UI")


def txt(slide, x, y, w, h, lines, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.TOP,
        rtl=True):
    """lines: list of (text, size, bold, color, extra_dict)."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    for i, item in enumerate(lines):
        text, size, bold, color = item[0], item[1], item[2], item[3]
        extra = item[4] if len(item) > 4 else {}
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = extra.get("align", align)
        _set_ar(p, extra.get("rtl", rtl))
        p.space_after = Pt(extra.get("space_after", 4))
        if "line_spacing" in extra:
            p.line_spacing = extra["line_spacing"]
        run = p.add_run()
        run.text = text
        _style_run(run, size, bold, color, mono=extra.get("mono", False))
    return tb


def rect(slide, x, y, w, h, fill, line=None, line_w=1.0, round_=False, radius=0.08):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if round_ else MSO_SHAPE.RECTANGLE, x, y, w, h)
    if round_:
        try:
            shp.adjustments[0] = radius
        except Exception:
            pass
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    return shp


def chip(slide, x, y, w, h, text, fill, fg, size=11, bold=True, line=None):
    shp = rect(slide, x, y, w, h, fill, line=line, round_=True, radius=0.5)
    tf = shp.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.06)
    tf.margin_top = tf.margin_bottom = Inches(0.01)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _set_ar(p)
    run = p.add_run()
    run.text = text
    _style_run(run, size, bold, fg)
    return shp


def pic_fit(slide, path, x, y, max_w, max_h, border=True):
    path = Path(path)
    if not path.exists():
        return None
    iw, ih = Image.open(path).size
    scale = min(max_w / iw, max_h / ih)
    w, h = int(iw * scale), int(ih * scale)
    px = x + int((max_w - w) / 2)
    py = y + int((max_h - h) / 2)
    if border:
        rect(slide, px - Emu(19050), py - Emu(19050), w + Emu(38100), h + Emu(38100),
             PANEL, line=BORDER, line_w=1.2)
    return slide.shapes.add_picture(str(path), px, py, width=w, height=h)


def header(slide, ar_title, en_sub="", accent=CYAN):
    rect(slide, 0, 0, W, Inches(0.06), accent)
    rect(slide, W - Inches(3.35), Inches(0.30), Inches(0.09), Inches(0.78), accent)
    txt(slide, Inches(0.6), Inches(0.30), Inches(8.95), Inches(0.6),
        [(ar_title, 24, True, TEXT)])
    if en_sub:
        txt(slide, Inches(0.6), Inches(0.84), Inches(8.95), Inches(0.34),
            [(en_sub, 12, False, MUTED, {"rtl": False, "align": PP_ALIGN.RIGHT})])
    footer(slide)


def footer(slide):
    txt(slide, Inches(0.55), Inches(7.08), Inches(4.4), Inches(0.3),
        [("StegoNexus · Kali Linux · 2026", 9.5, False, MUTED,
          {"rtl": False, "align": PP_ALIGN.LEFT})])
    chip(slide, Inches(12.62), Inches(7.05), Inches(0.5), Inches(0.3),
         str(SLIDE_NO["n"]), PANEL2, CYAN, size=10)


def card(slide, x, y, w, h, title, lines, accent=CYAN, title_size=13.5,
         body_size=11, fill=PANEL):
    rect(slide, x, y, w, h, fill, line=BORDER, line_w=1.0, round_=True, radius=0.05)
    rect(slide, x, y, Inches(0.07), h, accent)
    items = [(title, title_size, True, accent, {"space_after": 5})]
    for ln in lines:
        items.append((ln, body_size, False, TEXT, {"space_after": 4, "line_spacing": 1.04}))
    txt(slide, x + Inches(0.22), y + Inches(0.16), w - Inches(0.42), h - Inches(0.3),
        items)


def stat(slide, x, y, w, big, small, color=CYAN, big_size=30):
    rect(slide, x, y, w, Inches(1.12), PANEL2, line=BORDER, line_w=1.0, round_=True)
    txt(slide, x, y + Inches(0.12), w, Inches(0.55),
        [(big, big_size, True, color, {"align": PP_ALIGN.CENTER, "rtl": False})])
    txt(slide, x + Inches(0.06), y + Inches(0.74), w - Inches(0.12), Inches(0.34),
        [(small, 10.5, False, MUTED, {"align": PP_ALIGN.CENTER})])


def caption(slide, x, y, w, text_):
    chip(slide, x, y, w, Inches(0.3), text_, PANEL2, CYAN, size=9.5, bold=False)


# ================================================================= S1 title
s = new_slide()
rect(s, 0, 0, W, Hh, BG)
rect(s, 0, 0, W, Inches(0.10), CYAN)
rect(s, 0, Hh - Inches(0.10), W, Inches(0.10), CYAN)
for i, cx in enumerate((Inches(11.2), Inches(12.1), Inches(11.65))):
    ring = s.shapes.add_shape(MSO_SHAPE.OVAL, cx, Inches(0.6 + 0.7 * i),
                              Inches(1.4 - 0.3 * i), Inches(1.4 - 0.3 * i))
    ring.fill.background()
    ring.line.color.rgb = PANEL2
    ring.line.width = Pt(1.2)
    ring.shadow.inherit = False
chip(s, Inches(4.72), Inches(1.10), Inches(3.9), Inches(0.44),
     "مشروع مادة إخفاء البيانات والتحليل الجنائي الرقمي", PANEL2, CYAN, size=13)
txt(s, Inches(1.2), Inches(1.85), Inches(10.93), Inches(1.25),
    [("StegoNexus", 60, True, TEXT, {"align": PP_ALIGN.CENTER, "rtl": False})])
txt(s, Inches(1.2), Inches(3.02), Inches(10.93), Inches(0.6),
    [("منصة متكاملة لإخفاء واستخراج البيانات وتحليل البرمجيات الخبيثة والتحليل الجنائي الرقمي",
      19, True, CYAN, {"align": PP_ALIGN.CENTER})])
txt(s, Inches(1.2), Inches(3.72), Inches(10.93), Inches(0.42),
    [("Hide it. Extract it. Analyze it. Verify it. Investigate it. Document it. Report it.",
      13, False, MUTED, {"align": PP_ALIGN.CENTER, "rtl": False})])
for i, (t, c) in enumerate([("Python + PySide6", CYAN), ("Kali Linux", GREEN),
                            ("SQLite + AES-256-GCM", AMBER), ("10 محركات أصلية", VIOLET)]):
    chip(s, Inches(3.02 + i * 1.85), Inches(4.45), Inches(1.72), Inches(0.4),
         t, PANEL, c, size=11)
rect(s, Inches(3.47), Inches(5.30), Inches(6.4), Inches(0.012), BORDER)
txt(s, Inches(1.2), Inches(5.52), Inches(10.93), Inches(1.25),
    [("تطوير وإعداد:", 12, False, MUTED, {"align": PP_ALIGN.CENTER, "space_after": 2}),
     ("Mohammed Moneer Al-absi", 20, True, TEXT,
      {"align": PP_ALIGN.CENTER, "rtl": False, "space_after": 3}),
     ("إشراف: ..............................................   ·   العام الجامعي 2026",
      12, False, MUTED, {"align": PP_ALIGN.CENTER})])

# ================================================================= S2 agenda
s = new_slide()
header(s, "أجندة العرض", "Agenda")
agenda = [
    ("1", "المشكلة والأهداف", "لماذا هذه الأداة؟"),
    ("2", "البنية المعمارية", "PySide6 + خدمات + SQLite"),
    ("3", "الإطار الجنائي", "قضايا · أدلة · تجزئة · سجل"),
    ("4", "الميتاداتا والفورنسيك", "ExifTool · Triage"),
    ("5", "الإخفاء: نص وصورة", "LSB + Key · Steghide"),
    ("6", "الإخفاء: صوت وفيديو", "LSB · Phase · DSSS · EOF"),
    ("7", "الشبكة والملفات التنفيذية", "IPv4-ID · Overlay/Slack"),
    ("8", "الأمان والتحقق والخاتمة", "34 اختبارًا · 36 خطوة موثقة"),
]
for i, (num, t, sub) in enumerate(agenda):
    col, row = i % 2, i // 2
    x = Inches(0.75) + col * Inches(6.05)
    y = Inches(1.55) + row * Inches(1.32)
    rect(s, x, y, Inches(5.75), Inches(1.1), PANEL, line=BORDER, line_w=1, round_=True)
    chip(s, x + Inches(5.75 - 0.75), y + Inches(0.25), Inches(0.6), Inches(0.6),
         num, PANEL2, CYAN, size=17)
    txt(s, x + Inches(0.25), y + Inches(0.16), Inches(4.7), Inches(0.45),
        [(t, 15.5, True, TEXT)])
    txt(s, x + Inches(0.25), y + Inches(0.62), Inches(4.7), Inches(0.4),
        [(sub, 11, False, MUTED)])

# ================================================================= S3 problem
s = new_slide()
header(s, "المشكلة والحل", "Problem & Solution", accent=AMBER)
card(s, Inches(6.85), Inches(1.5), Inches(5.85), Inches(3.6),
     "المشكلة", [
         "أدوات الإخفاء في المقرر متفرقة: كل أداة تقنية واحدة فقط ومنصة واحدة",
         "OpenPuff وDeepSound وCyberHide تعمل على Windows حصرًا — لا تعمل على Kali",
         "لا ربط بين الإخفاء والتحليل الجنائي وتوثيق القضية والتقارير",
         "لا توجد لغة موحدة لإثبات أن النتيجة حقيقية لا مزيفة"],
     accent=RED)
card(s, Inches(0.62), Inches(1.5), Inches(5.95), Inches(3.6),
     "الحل: StegoNexus", [
         "منصة موحدة على Kali تنفذ كل تقنيات المقرر بمحركات أصلية مكتوبة خصيصًا",
         "تدمج الأدوات الخارجية الحقيقية: ExifTool، Steghide، Binwalk، FFmpeg، tshark",
         "دورة تحقيق كاملة: قضية ← أدلة بتجزئاتها ← نتائج ← تقارير PDF/HTML/JSON",
         "سياسة صدق صريحة: ملصق حالة لكل خاصية وسجل تدقيق لكل إجراء"],
     accent=GREEN)
rect(s, Inches(0.62), Inches(5.4), Inches(12.08), Inches(1.25), PANEL2,
     line=BORDER, line_w=1, round_=True)
txt(s, Inches(0.95), Inches(5.58), Inches(11.4), Inches(0.95),
    [("الهدف: تغطية 100% من متطلبات المقرر — عرض وحقن البيانات الوصفية، الإخفاء والاستخراج في النص والصورة "
      "والصوت والفيديو والشبكة والملفات التنفيذية (البرامج الضارة/الفيروسات) — بأكثر من تقنية لكل وسيط، مع إثبات قياسٍ لكل نتيجة.",
      13.5, True, CYAN, {"line_spacing": 1.15})])

# ================================================================= S4 architecture
s = new_slide()
header(s, "البنية المعمارية", "Architecture — layered, one source of truth")
# layer: front-ends
rect(s, Inches(2.2), Inches(1.5), Inches(8.9), Inches(0.85), PANEL2, line=BORDER, round_=True)
txt(s, Inches(2.4), Inches(1.63), Inches(8.5), Inches(0.6),
    [("واجهات الاستخدام:  PySide6 GUI — 20 شاشة (ثيم داكن/فاتح، عمليات غير متجمدة)   |   CLI تفاعلي",
      12.5, True, TEXT, {"align": PP_ALIGN.CENTER})])
arrow = s.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(6.42), Inches(2.42), Inches(0.5), Inches(0.5))
arrow.fill.solid(); arrow.fill.fore_color.rgb = CYAN; arrow.line.fill.background(); arrow.shadow.inherit = False
rect(s, Inches(2.2), Inches(2.98), Inches(8.9), Inches(0.85), PANEL2, line=BORDER, round_=True)
txt(s, Inches(2.4), Inches(3.11), Inches(8.5), Inches(0.6),
    [("17 واجهة خدمة (Service Facades): تحقق من المدخلات ← تنفيذ ← تسجيل في قاعدة البيانات وسجل التدقيق",
      12.5, True, TEXT, {"align": PP_ALIGN.CENTER})])
arrow = s.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(6.42), Inches(3.9), Inches(0.5), Inches(0.5))
arrow.fill.solid(); arrow.fill.fore_color.rgb = CYAN; arrow.line.fill.background(); arrow.shadow.inherit = False
# engines row
engines = [("10 محركات إخفاء أصلية", "lsb_text/image/audio · phase · DSSS · container · video_lsb · pe_stego", CYAN),
           ("ToolExecutor آمن", "أدوات خارجية بلا shell=True: exiftool · steghide · binwalk · ffmpeg · tshark", GREEN),
           ("تحليل دفاعي", "PE · ELF · Office · IOC · evasion catalogue", AMBER)]
for i, (t, sub, c) in enumerate(engines):
    x = Inches(2.2) + i * Inches(3.05)
    rect(s, x, Inches(4.46), Inches(2.85), Inches(1.25), PANEL, line=c, line_w=1.2, round_=True)
    txt(s, x + Inches(0.12), Inches(4.6), Inches(2.61), Inches(0.42),
        [(t, 12, True, c, {"align": PP_ALIGN.CENTER})])
    txt(s, x + Inches(0.12), Inches(5.02), Inches(2.61), Inches(0.62),
        [(sub, 9.5, False, MUTED, {"align": PP_ALIGN.CENTER, "rtl": False})])
arrow = s.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(6.42), Inches(5.78), Inches(0.5), Inches(0.42))
arrow.fill.solid(); arrow.fill.fore_color.rgb = CYAN; arrow.line.fill.background(); arrow.shadow.inherit = False
rect(s, Inches(2.2), Inches(6.24), Inches(8.9), Inches(0.62), PANEL2, line=BORDER, round_=True)
txt(s, Inches(2.4), Inches(6.33), Inches(8.5), Inches(0.45),
    [("التخزين: SQLite بوضع WAL — قضايا · أدلة وتجزئاتها · نتائج · تحليلات · تقارير · سجل تدقيق (لوحة المعلومات محسوبة منه كليًا)",
      11.5, True, TEXT, {"align": PP_ALIGN.CENTER})])

# ================================================================= S5 honesty
s = new_slide()
header(s, "سياسة الصدق — لغة الحالات الموحدة", "Honesty policy: a fixed status vocabulary")
labels = [
    ("IMPLEMENTED", "محرك أصلي كتبناه واختبرناه", GREEN, "10 محركات إخفاء + التحليل الجنائي"),
    ("INTEGRATED", "أداة خارجية حقيقية مدمجة فعلًا", CYAN, "ExifTool · Steghide · FFmpeg · Binwalk"),
    ("REFERENCE", "أداة مقرر نشرحها ولا نزيّفها", AMBER, "OpenPuff · CyberHide · DeepSound · Coagula"),
    ("EXTERNAL", "أداة نظام يمكن إطلاقها", VIOLET, "Wireshark · Audacity"),
    ("UNAVAILABLE", "غير مثبتة — تُعلن بصدق", RED, "أي أداة غائبة تظهر هكذا، لا نتائج ملفقة"),
]
y = Inches(1.55)
for name, mean, color, ex in labels:
    rect(s, Inches(0.65), y, Inches(12.05), Inches(0.92), PANEL, line=BORDER, round_=True)
    chip(s, Inches(10.7), y + Inches(0.21), Inches(1.85), Inches(0.5), name, color, INK, size=12)
    txt(s, Inches(4.3), y + Inches(0.13), Inches(6.25), Inches(0.4), [(mean, 13, True, TEXT)])
    txt(s, Inches(0.85), y + Inches(0.5), Inches(9.7), Inches(0.36),
        [(ex, 10.5, False, MUTED, {"rtl": False, "align": PP_ALIGN.RIGHT})])
    y += Inches(1.06)
rect(s, Inches(0.65), Inches(6.82), Inches(12.05), Inches(0.02), BORDER)

# ================================================================= S6 forensic frame
s = new_slide()
header(s, "الإطار الجنائي: القضية والأدلة والتجزئة", "Case management, evidence & integrity")
steps = [("قضية", "C.create"), ("استيراد دليل", "SHA-256 فوري"), ("نتائج", "Findings"),
         ("تقارير", "PDF/HTML/JSON")]
x = Inches(0.75)
for i, (t, sub) in enumerate(steps):
    ch = s.shapes.add_shape(MSO_SHAPE.CHEVRON, x, Inches(1.6), Inches(3.05), Inches(0.85))
    ch.fill.solid(); ch.fill.fore_color.rgb = PANEL2; ch.line.color.rgb = CYAN
    ch.line.width = Pt(1.2); ch.shadow.inherit = False
    tf = ch.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; _set_ar(p)
    r = p.add_run(); r.text = t; _style_run(r, 14, True, TEXT)
    x += Inches(3.0)
pic_fit(s, SHOTS / "cases.png", Inches(6.7), Inches(2.75), Inches(6.0), Inches(3.55))
caption(s, Inches(8.9), Inches(6.32), Inches(3.4), "لقطة حقيقية: قضية وأدلة مستوردة")
card(s, Inches(0.65), Inches(2.75), Inches(5.75), Inches(3.55), "ماذا يحدث فور الاستيراد؟", [
    "حساب 4 تجزئات للدليل: MD5 · SHA-1 · SHA-256 · SHA-512",
    "فتح سلسلة العهدة وربط الدليل بالقضية النشطة",
    "الأصل لا يُعدَّل أبدًا — كل عمليات الإخفاء/الحقن على نسخ عمل",
    "زر Verify: مقارنة التجزئة المخزنة بالحالية ← MATCH / MISMATCH",
    "أرقام من تشغيلنا الموثق: القضية #22 — 6 أدلة (PNG/JPG/WAV/MP4/PCAP/EXE) بتجزئاتها كاملة"],
    accent=GREEN)

# ================================================================= S7 hashing
s = new_slide()
header(s, "التجزئة والتحقق من السلامة", "Hashing — MD5 / SHA-1 / SHA-256 / SHA-512")
pic_fit(s, SHOTS / "hashing.png", Inches(6.7), Inches(1.5), Inches(6.0), Inches(4.6))
caption(s, Inches(8.9), Inches(6.15), Inches(3.4), "حساب ومقارنة حقيقية داخل الأداة")
card(s, Inches(0.65), Inches(1.5), Inches(5.75), Inches(2.2), "لماذا 4 خوارزميات؟", [
    "SHA-256/512: مرجع السلامة (MD5 وSHA-1 مكسوران تصادميًا — للتوثيق فقط)",
    "Compute: الأربعة دفعة واحدة لملف حتى 4GB",
    "Compare: ملفان ← MATCH / MISMATCH + فرق الحجم + استنتاج نصي"],
    accent=CYAN)
card(s, Inches(0.65), Inches(3.9), Inches(5.75), Inches(2.2), "دورها في إثباتنا", [
    "قبل/بعد كل حقن: تجزئة الأصل متطابقة ← الأصل لم يُمَس",
    "بعد كل استخراج: تجزئة المسترجَع = الأصل ← تطابق بايت-ببايت",
    "من تشغيلنا: كل جولات الإخفاء الـ 12 انتهت بتطابق True"],
    accent=GREEN)

# ================================================================= S8 metadata
s = new_slide()
header(s, "البيانات الوصفية: عرض وحقن وإزالة", "Metadata — read / inject / strip / compare (ExifTool)")
pic_fit(s, EVID / "s06.png", Inches(6.7), Inches(1.5), Inches(6.0), Inches(4.35))
caption(s, Inches(8.75), Inches(5.95), Inches(3.7), "حقن 3 وسوم — تجزئة الأصل unchanged=True")
card(s, Inches(0.65), Inches(1.5), Inches(5.75), Inches(3.1), "العمليات الأربع", [
    "Read: عرض كل الوسوم عبر exiftool (قرأنا 32 وسمًا من JPEG فعليًا)",
    "Inject: كتابة وسوم (Comment/Artist/Copyright…) في نسخة جديدة حصرًا",
    "Compare: فرق قبل/بعد وسمًا بوسم (مضاف/محذوف/معدَّل)",
    "Strip: نسخة نظيفة بلا وسوم حساسة للمشاركة الآمنة"],
    accent=CYAN)
card(s, Inches(0.65), Inches(4.8), Inches(5.75), Inches(1.85), "لماذا هي مهمة جنائيًا؟", [
    "تثبت المنشأ والتوقيت والجهاز — وقد تسرّب موقعًا جغرافيًا",
    "الحقن نفسه قناة إخفاء خفيفة: بيانات تعسفية داخل وسوم تعسفية"],
    accent=AMBER)

# ================================================================= S9 forensics
s = new_slide()
header(s, "التحليل الجنائي للملفات", "Forensics — file · strings · entropy · binwalk · foremost · steghide · zsteg")
pic_fit(s, SHOTS / "forensics.png", Inches(6.7), Inches(1.5), Inches(6.0), Inches(4.6))
caption(s, Inches(8.9), Inches(6.15), Inches(3.4), "زر Triage يشغل كل الأدوات دفعة واحدة")
tools_rows = [
    ("file", "النوع الحقيقي من البصمة — يكشف انتحال الامتداد"),
    ("strings", "سلاسل مقروءة: روابط وعناوين ومؤشرات"),
    ("entropy", "عشوائية شانون 0–8: العالية مؤشر ضغط/تشفير"),
    ("binwalk · foremost", "carving لاستخراج ملفات مضمّنة بالتوقيع"),
    ("steghide --info · zsteg", "هل يوجد إخفاء؟ وأي نوع؟"),
]
y = Inches(1.55)
for name, desc in tools_rows:
    rect(s, Inches(0.65), y, Inches(5.75), Inches(0.78), PANEL, line=BORDER, round_=True)
    txt(s, Inches(0.85), y + Inches(0.09), Inches(2.05), Inches(0.6),
        [(name, 11.5, True, CYAN, {"rtl": False, "align": PP_ALIGN.LEFT})])
    txt(s, Inches(2.95), y + Inches(0.09), Inches(3.3), Inches(0.62), [(desc, 10.5, False, TEXT)])
    y += Inches(0.92)
rect(s, Inches(0.65), y + Inches(0.02), Inches(5.75), Inches(0.62), PANEL2, line=BORDER, round_=True)
txt(s, Inches(0.8), y + Inches(0.1), Inches(5.5), Inches(0.5),
    [("من تشغيلنا: PNG ضوضائي ← إنتروبيا 7.9988 · 330 سلسلة — الإنتروبيا العالية وحدها ليست دليلًا (الحامل نفسه ضوضاء)",
      10, True, AMBER, {"line_spacing": 1.05})])

# ================================================================= S10 text
s = new_slide()
header(s, "الإخفاء في النص — LSB مع مفتاح", "Text steganography: native LSB + key ordering")
pic_fit(s, SHOTS / "text.png", Inches(6.7), Inches(1.5), Inches(6.0), Inches(4.6))
caption(s, Inches(8.9), Inches(6.15), Inches(3.4), "Encode/Decode حقيقي داخل الأداة")
card(s, Inches(0.65), Inches(1.5), Inches(5.75), Inches(3.55), "كيف يعمل المحرك؟", [
    "1) اختيار الأحرف المؤهلة فقط: حروف/أرقام يبقى قلب LSB لها داخل المجموعة",
    "2) تأطير الرسالة: بصمة SNX1 + فحص مفتاح + طول + CRC-32",
    "3) ضغط zlib ثم تقنيع XOR بمجرى SHA-256-CTR مشتق من المفتاح",
    "4) كتابة البتات بترتيب Fisher-Yates محكوم بالمفتاح — انتشار في كامل المستند",
    "5) الاستخراج عكسي بنفس المفتاح ← مفتاح خاطئ = خطأ صريح"],
    accent=CYAN)
card(s, Inches(0.65), Inches(5.2), Inches(5.75), Inches(1.45), "الكشف", [
    "قلب LSB يغير الحرف ±1 فقط (a→b) — التضمين الكثيف يصنع انحياز LSB قابلًا للقياس بزر Analyse"],
    accent=AMBER)

# ================================================================= S11 image
s = new_slide()
header(s, "الإخفاء في الصور — تقنيتان", "Images: native LSB (PNG) + Steghide (JPEG)")
pic_fit(s, SHOTS / "image.png", Inches(6.7), Inches(1.5), Inches(6.0), Inches(4.6))
caption(s, Inches(8.9), Inches(6.15), Inches(3.4), "اختيار المحرك: native / steghide")
card(s, Inches(0.65), Inches(1.5), Inches(5.75), Inches(2.35), "المحرك الأصلي — LSB مكاني", [
    "استبدال بت LSB في قنوات البكسل — حامل ومخرج بلا فقد (PNG/BMP)",
    "ترويسة ثابتة + جسم بترتيب numpy مشتق من SHA-256(ملح+مفتاح)",
    "من تشغيلنا: 73 بايت داخل 256×256 ← استرجاع مطابق بايت-ببايت"],
    accent=CYAN)
card(s, Inches(0.65), Inches(4.05), Inches(5.75), Inches(2.35), "Steghide — مدمجة INTEGRATED", [
    "أداة خارجية حقيقية (مجال تحويلي، نظرية المخططات، ضغط + تشفير داخلي)",
    "JPEG/BMP/WAV — لا تدعم PNG (يظهر UNSUPPORTED بصدق)",
    "من تشغيلنا: إخفاء واستخراج على JPEG بكلمة مرور ← تطابق كامل"],
    accent=GREEN)
chip(s, Inches(6.95), Inches(6.5), Inches(5.6), Inches(0.4),
     "لماذا لا LSB على JPEG؟ ضغط DCT الفائد يدمر البتات — لذا Steghide تعمل في المجال التحويلي",
     PANEL2, AMBER, size=10.5, bold=False)

# ================================================================= S12 audio
s = new_slide()
header(s, "الإخفاء في الصوت — ثلاث تقنيات", "Audio: LSB · Phase Coding · Spread Spectrum (DSSS)")
pic_fit(s, SHOTS / "audio.png", Inches(8.35), Inches(1.5), Inches(4.35), Inches(4.35))
caption(s, Inches(9.35), Inches(5.95), Inches(2.6), "قائمة اختيار التقنية + SNR")
cards = [
    ("1) LSB", CYAN, [
        "استبدال LSB في عينات PCM 16-بت",
        "خطوة البت = 1/32768 من المدى — دون عتبة السمع",
        "السعة الأعلى والأبسط؛ هشة لأي إعادة ترميز"]),
    ("2) Phase Coding", GREEN, [
        "FFT لقطع 1024 عينة؛ فرض فرق طور ±π/4 حسب البت",
        "المقادير محفوظة — الاسمع لا يلاحظ",
        "أقوى ضد التحليل البسيط؛ يحتاج حاملًا ≥15 ث"]),
    ("3) DSSS", VIOLET, [
        "كل بت ينتشر عبر متتالية ضوضاء ±1 مشتقة من المفتاح",
        "طاقة الرسالة تحت أرضية الضوضاء",
        "استخراج أعمى بالمفتاح فقط (حامل 30ث)"]),
]
for i, (t, c, lines) in enumerate(cards):
    card(s, Inches(0.65), Inches(1.5 + i * 1.62), Inches(7.4), Inches(1.5), t, lines, accent=c,
         title_size=12.5, body_size=10.5)
chip(s, Inches(8.35), Inches(6.4), Inches(4.35), Inches(0.5),
     "مقاس فعليًا: SNR ≈ 97dB لـ LSB · استرجاع مطابق للتقنيات الثلاث", PANEL2, GREEN, size=11)

# ================================================================= S13 video
s = new_slide()
header(s, "الإخفاء في الفيديو — تقنيتان", "Video: FFV1 LSB pipeline + custom AES-EOF container")
pic_fit(s, SHOTS / "video.png", Inches(8.35), Inches(1.5), Inches(4.35), Inches(4.35))
caption(s, Inches(9.35), Inches(5.95), Inches(2.6), "Hide / Extract / Detect")
card(s, Inches(0.65), Inches(1.5), Inches(7.4), Inches(2.5), "أ) FFV1 LSB — خط أنابيب بلا فقد", [
    "ffprobe (حقائق) ← ffmpeg يفكك الإطارات إلى PNG ← تضمين LSB إطارًا بإطار بترتيب مفتاحي "
    "← إعادة ترميز FFV1 داخل MKV (فائد صفر) ← تحقق تلقائي بإعادة الاستخراج",
    "الأداة ترفض إخراج mp4 مقصودًا: أي إعادة ضغط فائدة تدمر بتات LSB — درس تعليمي مقصود"],
    accent=CYAN)
card(s, Inches(0.65), Inches(4.2), Inches(7.4), Inches(2.5), "ب) حاوية EOF المخصصة — مشفرة بالكامل", [
    "بنية: بصمة SNXEOF0001 + ملح + nonce + اسم الملف + نص مشفر AES-256-GCM، وتُلحق بعد نهاية الفيديو مع trailing بالطول",
    "مشتق المفتاح PBKDF2-SHA256 بـ 200,000 تكرار — مفتاح خاطئ = فشل تحقق GCM صريح",
    "المشغل يقرأ الفيديو طبيعيًا 100%؛ Detect يكشفها من آخر 18 بايت دون مفتاح",
    "تصريح صريح في الواجهة: حاوية أكاديمية خاصة — ليست OpenPuff ولا متوافقة معها"],
    accent=VIOLET)

# ================================================================= S14 network
s = new_slide()
header(s, "الإخفاء في الشبكة — قناة IPv4 Identification", "Network steganography: the IPv4-ID covert channel")
# IPv4 header diagram
rect(s, Inches(0.65), Inches(1.5), Inches(12.05), Inches(1.5), PANEL, line=BORDER, round_=True)
txt(s, Inches(0.9), Inches(1.62), Inches(11.5), Inches(0.35),
    [("ترويسة IPv4 — الحقل المستغل:", 12.5, True, TEXT)])
fields = [("الإصدار/IHL", MUTED, 2.2), ("الخدمات", MUTED, 1.5), ("الطول الكلي", MUTED, 1.7),
          ("Identification ← 15 بت حمولة + بت parity", CYAN, 3.6), ("الراوترات لا توحّده", GREEN, 2.9)]
x = Inches(0.9)
for name, c, w in fields:
    chip(s, x, Inches(2.05), Inches(w), Inches(0.55), name, PANEL2, c, size=10.5)
    x += Inches(w + 0.12)
txt(s, Inches(0.9), Inches(2.65), Inches(11.5), Inches(0.32),
    [("تأطير SNXNET1: عدد القطع + طول + CRC-32 ← قطع 15-بت؛ بت parity على فهرس القطعة يكشف الفقد وإعادة الترتيب",
      10.5, False, MUTED)])
pic_fit(s, SHOTS / "network.png", Inches(8.35), Inches(3.25), Inches(4.35), Inches(3.0))
caption(s, Inches(9.5), Inches(6.3), Inches(2.2), "شاشة المختبر الشبكي")
card(s, Inches(0.65), Inches(3.25), Inches(7.4), Inches(1.55), "ثلاث أدوات", [
    "Preview: خريطة قيم IP-ID دون أي إرسال (تعليمي) — أرسلنا حمولة حقيقية وقسمناها فعلًا",
    "Send/Receive: قناة UDP أساسية غير سرية (مقارنة) — نجحت فعليًا: SUCCESS/SUCCESS وتطابق",
    "القناة السرية IPv4-ID: تتطلب root + وضع المختبر المصرَّح (أثبتناها PASS في preflight)"],
    accent=CYAN, body_size=10.5)
card(s, Inches(0.65), Inches(4.95), Inches(7.4), Inches(1.55), "الوجه الجنائي: مفسر PCAP", [
    "تحليل إحصائي للاعتراض: اعتراضنا (17 حزمة) أعطى ثقة High لبنية CRC متسقة",
    "الواجهة نفسها تعلن: «الشذوذ مؤشر لا دليل» — قاعدة أكاديمية ذهبية"],
    accent=AMBER, body_size=10.5)

# ================================================================= S15 exec stego 1
s = new_slide()
header(s, "الإخفاء التنفيذي: البرامج الضارة والفيروسات", "Executable steganography: PE overlay & section slack", accent=RED)
# PE layout diagram
px, py, pw, ph = Inches(0.9), Inches(1.75), Inches(11.5), Inches(1.7)
rect(s, px, py, pw, ph, PANEL, line=BORDER, round_=True)
segs = [("ترويسات DOS/PE", PANEL2, TEXT, 2.3), ("قسم .text", PANEL2, TEXT, 2.3),
        ("حشو القسم (Slack) ← الحاوية المخفية", GREEN, INK, 3.3),
        ("overlay ← الحاوية الملحقة", AMBER, INK, 2.6)]
x = px + Inches(0.15)
for name, f, fg, w in segs:
    chip(s, x, py + Inches(0.55), Inches(w), Inches(0.6), name, f, fg, size=10.5)
    x += Inches(w + 0.1)
txt(s, px + Inches(0.15), py + Inches(1.25), Inches(11.2), Inches(0.35),
    [("بنية PE: الحشو = فرق VirtualSize وSizeOfRawData — لا يقرأه المحمّل إطلاقًا؛ overlay يقع بعد آخر قسم",
      10.5, False, MUTED)])
card(s, Inches(0.65), Inches(3.85), Inches(5.9), Inches(2.7), "تقنية Overlay", [
    "إلحاق حاوية AES-256-GCM بعد آخر قسم + trailer بالطول",
    "النمط الكلاسيكي لـ dropper/installer: حمولة ثانية داخل حامل سليم",
    "أثر جنائي: الحجم يزيد ← يكشفها مقارنة الحجم بنهاية جدول الأقسام",
    "من تشغيلنا: +150 بايت ظاهرة وكُشفت بنجاح"],
    accent=AMBER)
card(s, Inches(6.8), Inches(3.85), Inches(5.9), Inches(2.7), "تقنية Section Slack", [
    "كتابة الحاوية داخل حشو القسم وملء الباقي أصفارًا",
    "الحجم لا يتغير إطلاقًا ← قياس الحجم وحده لا يكشف شيئًا",
    "يكشفها فقط تحليل جدول الأقسام وفحص الحشو بايت-ببايت (زر Scan)",
    "من تشغيلنا: 73 بايت في حامل 2048 ← الناتج 2048 بالضبط"],
    accent=GREEN)

# ================================================================= S16 exec stego 2 evidence
s = new_slide()
header(s, "الإخفاء التنفيذي: التجربة الموثقة كاملة", "Executable stego — the documented real run", accent=GREEN)
shots = [
    ("s30.png", "Hide (slack)", "إخفاء 73 بايت — الحجم لم يتغير"),
    ("s31.png", "Scan", "كشف: blob في قسم .text"),
    ("s32.png", "Extract", "استخراج بتطابق SHA-256"),
    ("s33.png", "Static flag", "التحليل الساكن أشارة تلقائيًا"),
]
for i, (f, t, cap) in enumerate(shots):
    x = Inches(0.62) + i * Inches(3.08)
    pic_fit(s, EVID / f, x, Inches(1.6), Inches(2.9), Inches(3.3))
    caption(s, x + Inches(0.2), Inches(5.0), Inches(2.5), f"{t} — {cap}")
rect(s, Inches(0.62), Inches(5.55), Inches(12.08), Inches(1.15), PANEL2, line=BORDER, round_=True)
txt(s, Inches(0.9), Inches(5.7), Inches(11.5), Inches(0.9),
    [("حلقة مكتملة: إخفاء ← كشف ساكن ← استخراج ← إلواح تلقائي. لا تنفيذ للملف ولا فتحه بمحمل — كل شيء فحص بايتات على نسخ. "
      "وهذا يجيب مباشرة على متطلب «الإخفاء في البرامج الضارة والفيروسات» بأمانة وأمان",
      13, True, GREEN, {"line_spacing": 1.12})])

# ================================================================= S17 malware static
s = new_slide()
header(s, "تحليل البرمجيات الخبيثة — ساكن دفاعي فقط", "Malware static analysis — never executed", accent=RED)
pic_fit(s, SHOTS / "malware.png", Inches(6.7), Inches(1.5), Inches(6.0), Inches(4.6))
caption(s, Inches(8.9), Inches(6.15), Inches(3.4), "تقرير ساكن كامل داخل الواجهة")
card(s, Inches(0.65), Inches(1.5), Inches(5.75), Inches(3.0), "ماذا يفحص؟", [
    "فحص PE الكامل: أقسام حزم معروفة (UPX/Themida)، إنتروبيا قسم ≥ 7.2، نقطة دخول مشبوهة، توقيت ترجمة مستحيل",
    "انتحال امتدادات + محارف RTLO · timestomping (mtime مقابل ctime) · تمويه · PyInstaller · أرشيفات · ELF · Office",
    "استخراج IOC: روابط وعناوين وسلاسل مريبة"],
    accent=CYAN, body_size=10.5)
card(s, Inches(0.65), Inches(4.7), Inches(5.75), Inches(1.95), "قاعدة التقييم", [
    "الدرجة = 8 × عدد المؤشرات (سقف 100)",
    "الثقة بالارتباط: مؤشر واحد = Low · أقل من 3 = Medium · 3+ = High",
    "«مؤشر واحد لا يثبت شيئًا» — الإنتروبيا العالية في كل ملف مضغوط!"],
    accent=AMBER, body_size=10.5)

# ================================================================= S18 security
s = new_slide()
header(s, "الأمان والأخلاقيات — بلا استثناء", "Security & ethics constraints", accent=VIOLET)
cards = [
    ("قراءة-فقط افتراضيًا", GREEN, ["الأصل لا يُعدَّل أبدًا", "كل عملية على نسخة عمل",
                                    "إثبات قبل/بعد بتجزئة SHA-256"]),
    ("برمجيات خبيثة: ساكن فقط", RED, ["العينة لا تُنفَّذ إطلاقًا", "لا sandbox ولا detonation",
                                       "لا أي كود هجومي في المشروع"]),
    ("شبكة مقيدة", AMBER, ["مقفولة افتراضيًا — مفتاح مصرّح", "root للقناة السرية",
                            "وجهات: loopback / RFC1918 فقط"]),
    ("لا نتائج ملفقة", CYAN, ["أداة غائبة = UNAVAILABLE", "الشذوذ مؤشر لا دليل",
                               "حالات الطب العينات: TRAINING-SYNTHETIC"]),
]
for i, (t, c, lines) in enumerate(cards):
    x = Inches(0.65) + (i % 2) * Inches(6.15)
    y = Inches(1.55) + (i // 2) * Inches(2.5)
    card(s, x, y, Inches(5.9), Inches(2.3), t, lines, accent=c, title_size=14, body_size=11)

# ================================================================= S19 verification
s = new_slide()
header(s, "التحقق: كل رقم قابل لإعادة التشغيل", "Verification — measured, reproducible, honest", accent=GREEN)
stats = [
    ("34", "اختبار pytest ناجح", GREEN), ("36", "خطوة موثقة بلقطات وقياسات", CYAN),
    ("20/20", "واجهات GUI تُرسم بلا أخطاء", CYAN), ("11/11", "مسارات أزرار حقيقية", CYAN),
    ("READY", "preflight شامل (22 PASS بصلاحيات root)", GREEN), ("15/24", "أداة خارجية متاحة والباقي بصدق", AMBER),
    ("10/10", "جولات إخفاء/استخراج بتطابق كامل", GREEN), ("100%", "تغطية متطلبات المقرر", VIOLET),
]
for i, (big, small, c) in enumerate(stats):
    x = Inches(0.72) + (i % 4) * Inches(3.05)
    y = Inches(1.65) + (i // 4) * Inches(1.5)
    stat(s, x, y, Inches(2.85), big, small, color=c, big_size=26 if len(big) > 3 else 30)
rect(s, Inches(0.72), Inches(4.78), Inches(11.9), Inches(1.95), PANEL, line=BORDER, round_=True)
txt(s, Inches(1.0), Inches(4.96), Inches(11.3), Inches(1.6),
    [("كيف نثبت ذلك أمامك الآن؟", 14, True, CYAN, {"space_after": 8}),
     ("أمر واحد يعيد كل شيء: pytest · preflight · اختبار الواجهات · اختبار الأزرار · demo_end_to_end",
      12, False, TEXT, {"space_after": 5, "line_spacing": 1.12}),
     ("preflight ينفذ جولات إخفاء حقيقية ويقارن المستخرج بالأصل بايت-ببايت، وكل النواتج تُكتب في artifacts/ — "
      "والتقرير المصوَّر (36 خطوة) يوثق القياسات نفسها بلقطاتها", 12, False, TEXT, {"line_spacing": 1.12})])

# ================================================================= S20 cases A-D
s = new_slide()
header(s, "القضايا التدريبية A–D — مادة عرض جاهزة", "Synthetic training cases (labelled, reproducible)")
cases = [
    ("A", "ميتاداتا + صورة LSB", "حقن وسوم على نسخة + إخفاء/استخراج + إثبات أن الأصل سليم", CYAN),
    ("B", "صوت LSB", "SNR مقاس ~97dB واسترجاع مطابق", GREEN),
    ("C", "شبكة PCAP + خبيث ساكن", "ثقة High للاعتراض + تحليل ساكن دون تنفيذ", AMBER),
    ("D", "إخفاء تنفيذي (الجديد)", "slack + overlay ← كشف ← استخراج ← إلواح", RED),
]
for i, (letter, t, d, c) in enumerate(cases):
    x = Inches(0.72) + i * Inches(3.08)
    rect(s, x, Inches(1.6), Inches(2.9), Inches(3.2), PANEL, line=BORDER, round_=True)
    chip(s, x + Inches(0.95), Inches(1.85), Inches(1.0), Inches(0.7), letter, c, INK, size=22)
    txt(s, x + Inches(0.15), Inches(2.75), Inches(2.6), Inches(0.5),
        [(t, 13, True, TEXT, {"align": PP_ALIGN.CENTER})])
    txt(s, x + Inches(0.18), Inches(3.3), Inches(2.55), Inches(1.35),
        [(d, 10.5, False, MUTED, {"align": PP_ALIGN.CENTER, "line_spacing": 1.1})])
rect(s, Inches(0.72), Inches(5.05), Inches(11.9), Inches(1.5), PANEL2, line=BORDER, round_=True)
txt(s, Inches(1.0), Inches(5.2), Inches(11.3), Inches(1.2),
    [("قضايا المقرر الحقيقية؟", 13.5, True, CYAN, {"space_after": 3}),
     ("استوردها عبر Cases ← New Case ← Evidence ← Import — الخدمات مستقلة عن الصيغة ولا حاجة لأي تعديل في الكود. "
      "القضايا المدمجة موسومة TRAINING-SYNTHETIC أمانةً مع اللجنة.", 11.5, False, TEXT, {"line_spacing": 1.12})])

# ================================================================= S21 reports
s = new_slide()
header(s, "التوثيق والتقارير", "Reports & documentation pipeline")
pic_fit(s, SHOTS / "reports.png", Inches(6.7), Inches(1.5), Inches(6.0), Inches(4.6))
caption(s, Inches(8.9), Inches(6.15), Inches(3.4), "توليد PDF/HTML/JSON من السجلات")
card(s, Inches(0.65), Inches(1.5), Inches(5.75), Inches(2.3), "ثلاث صيغ من قاعدة البيانات", [
    "PDF موسوم بالهوية + HTML تفاعلي + JSON خام للأدلة",
    "تضم الأدلة وتجزئاتها والتحليلات والنتائج ولقطة حالة الأدوات",
    "من تشغيلنا: تقرير القضية الموثقة (PDF 171KB · HTML 110KB · JSON 56KB)"],
    accent=CYAN, body_size=10.5)
card(s, Inches(0.65), Inches(4.0), Inches(5.75), Inches(2.6), "طبقات التوثيق الأخرى", [
    "سجل التدقيق: من/متى/ماذا/النتيجة/التجزئة لكل إجراء",
    "توثيق docs/: دليل استخدام، معمارية، مصفوفة تتبع 23 متطلبًا، دليل مناقشة",
    "التقرير الشامل المصوَّر: 36 خطوة بقياساتها وشرح لكل لقطة",
    "دليل عربي مصور لكل خدمة — يعمل دون إنترنت"],
    accent=GREEN, body_size=10.5)

# ================================================================= S22 limitations
s = new_slide()
header(s, "الحدود والقيود — بصدق كامل", "Honest limitations", accent=AMBER)
lims = [
    ("أدوات Windows المرجعية", "OpenPuff/CyberHide/DeepSound/Coagula توثَّق REFERENCE — وبنينا محركات أصلية مكافئة تعمل على Kali"),
    ("تحليل ديناميكي محجوب", "لا تنفيذ للعينات عمدًا — قرار أمني/أخلاقي موثق، والتحليل ساكن فقط"),
    ("الشبكة تتطلب صلاحيات", "القناة السرية تحتاج root + وضع مختبر مصرَّح — وبدونها تظهر GATED بصدق"),
    ("الشذوذ ≠ إثبات", "أي قيمة غريبة في ترويسة مؤشر تحقيق وليست إدانة — الواجهة تعلن ذلك نصيًا"),
]
y = Inches(1.6)
for t, d in lims:
    rect(s, Inches(0.65), y, Inches(12.05), Inches(1.05), PANEL, line=BORDER, round_=True)
    chip(s, Inches(10.9), y + Inches(0.28), Inches(1.6), Inches(0.5), "قيود موثقة", PANEL2, AMBER, size=10.5)
    txt(s, Inches(0.9), y + Inches(0.12), Inches(9.8), Inches(0.4), [(t, 13.5, True, TEXT)])
    txt(s, Inches(0.9), y + Inches(0.53), Inches(9.8), Inches(0.45), [(d, 11, False, MUTED)])
    y += Inches(1.2)
txt(s, Inches(0.65), Inches(6.5), Inches(12.05), Inches(0.45),
    [("ذكر القيود بوضوح ليس ضعفًا — إنه الفرق بين أداة أكاديمية أمينة وأداة دعائية", 12.5, True, AMBER,
      {"align": PP_ALIGN.CENTER})])

# ================================================================= S23 conclusion
s = new_slide()
header(s, "الخلاصة", "Conclusion", accent=GREEN)
achv = [
    ("تغطية كاملة", "كل تقنيات المقرر في أداة واحدة: ميتاداتا · نص · صورة · صوت · فيديو · شبكة · تنفيذية"),
    ("محركات أصلية", "10 محركات مكتوبة يدويًا + دمج حقيقي لأدوات Kali الخارجية"),
    ("إثبات قياس", "34 اختبارًا · 36 خطوة موثقة · 12/12 جولة بتطابق بايت-ببايت · preflight READY"),
    ("نضج أكاديمي", "سياسة صدق · سجل تدقيق · قضايا وأدلة · تقارير · حدود معلنة"),
]
for i, (t, d) in enumerate(achv):
    y = Inches(1.55) + i * Inches(1.12)
    rect(s, Inches(0.65), y, Inches(12.05), Inches(0.98), PANEL, line=BORDER, round_=True)
    chip(s, Inches(11.55), y + Inches(0.24), Inches(0.95), Inches(0.5), str(i + 1), PANEL2, CYAN, size=15)
    txt(s, Inches(8.1), y + Inches(0.1), Inches(3.3), Inches(0.4), [(t, 13.5, True, CYAN)])
    txt(s, Inches(0.9), y + Inches(0.52), Inches(10.5), Inches(0.42), [(d, 11, False, TEXT)])
rect(s, Inches(0.65), Inches(6.15), Inches(12.05), Inches(0.85), PANEL2, line=GREEN, line_w=1.2, round_=True)
txt(s, Inches(0.95), Inches(6.3), Inches(11.4), Inches(0.6),
    [("«القيمة الحقيقية ليست أن كل أداة موجودة — بل أن المنصة تقول الحقيقة دائمًا عن ما فعلته وبأي أداة وبأي تجزئة»",
      13.5, True, GREEN, {"align": PP_ALIGN.CENTER, "line_spacing": 1.1})])

# ================================================================= S24 thanks
s = new_slide()
rect(s, 0, 0, W, Hh, BG)
rect(s, 0, 0, W, Inches(0.10), CYAN)
rect(s, 0, Hh - Inches(0.10), W, Inches(0.10), CYAN)
txt(s, Inches(1.2), Inches(2.3), Inches(10.93), Inches(1.1),
    [("شكرًا لحسن استماعكم", 44, True, TEXT, {"align": PP_ALIGN.CENTER})])
txt(s, Inches(1.2), Inches(3.55), Inches(10.93), Inches(0.5),
    [("نرحب بأسئلتكم — وكل رقم قلناه اليوم قابل لإعادة التشغيل أمامكم الآن", 16, False, CYAN,
      {"align": PP_ALIGN.CENTER})])
for i, t in enumerate(["عرض حي مباشر", "إعادة تشغيل الاختبارات", "التقرير المصوَّر (36 خطوة)"]):
    chip(s, Inches(3.47 + i * 2.25), Inches(4.6), Inches(2.05), Inches(0.5), t, PANEL, CYAN, size=11.5)
txt(s, Inches(1.2), Inches(5.75), Inches(10.93), Inches(0.4),
    [("تطوير وإعداد:", 12, False, MUTED, {"align": PP_ALIGN.CENTER})])
txt(s, Inches(1.2), Inches(6.15), Inches(10.93), Inches(0.45),
    [("Mohammed Moneer Al-absi", 15, True, TEXT, {"align": PP_ALIGN.CENTER, "rtl": False})])
txt(s, Inches(1.2), Inches(6.72), Inches(10.93), Inches(0.35),
    [("StegoNexus · 2026", 11, False, MUTED, {"align": PP_ALIGN.CENTER, "rtl": False})])

prs.save(str(OUT))
print(f"Saved {OUT} with {SLIDE_NO['n']} slides")
