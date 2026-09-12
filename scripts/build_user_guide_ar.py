#!/usr/bin/env python3
"""Build a self-contained Arabic (RTL) user guide for StegoNexus.

Every section explains, step by step, how to use one service in the GUI, and each
explanation is followed by a REAL screenshot of that service in action (embedded as
a base64 data URI so the file works offline and in the sandboxed preview).

Usage: python scripts/build_user_guide_ar.py
Writes: artifacts/real_verification/USER_GUIDE_AR.html
"""
from __future__ import annotations

import base64
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "artifacts" / "real_verification" / "screenshots_services"
OUT = ROOT / "artifacts" / "real_verification" / "USER_GUIDE_AR.html"


def uri(name: str) -> str:
    return "data:image/png;base64," + base64.b64encode((SHOTS / name).read_bytes()).decode()


SECTIONS = [
    # ------------------------------------------------------------ intro
    {"title": "قبل البدء: التشغيل والمفاهيم الأساسية", "steps": [
        "ثبّت الأدوات: <code>sudo ./scripts/install_kali.sh</code> ثم شغّل <code>./scripts/run.sh</code>.",
        "افحص كل الخدمات: <code>./scripts/preflight.sh</code> (يطبع PASS/FAIL لكل خدمة).",
        "المفهوم الأهم: الأداة <b>قراءة‑فقط افتراضياً</b> — لا يعدَّل أي دليل أصلي؛ كل العمليات على نُسَخ عمل، وكل إجراء يُسجَّل في سجل التدقيق (Investigation Logs).",
        "ابدأ دائماً بإنشاء «قضية» (Case) من صفحة Cases؛ معظم الخدمات تربط نتائجها بالقضية النشطة (تظهر أعلى اليمين).",
    ], "notes": [
        "المفتاح/كلمة المرور يجب ألا تقل عن 4 أحرف (تتحقق الأداة منها).",
        "النتائج تُعرض في «الكونسول» أسفل كل صفحة، وتظهر حالة العملية في الشارة أعلى الصفحة.",
    ], "shots": [("s01_cases_cases.png", "إنشاء قضية جديدة واستيراد دليل — كل الخدمات تُربط بالقضية النشطة.")]},

    # ------------------------------------------------------------ cases/evidence
    {"title": "1) إدارة القضايا والأدلة (Cases / Evidence)", "steps": [
        "من القائمة الجانبية: <b>Cases</b> ← زر إنشاء قضية جديدة ← أدخل العنوان والوصف والمحقِّق ← حفظ.",
        "حدّد القضية من الجدول لتصبح «نشطة» (تظهر أعلى النافذة).",
        "من صفحة <b>Evidence</b>: زر استيراد ← اختر ملف الدليل (صورة/صوت/فيديو/pcap/أرشيف…) ← يُسجَّل مع تجزئة SHA‑256 وسلسلة عهدة.",
        "لم يعُدَّل الأصل أبداً: استخدم «نسخة عمل» (Working Copy) من صفحة Evidence لأي تعديل.",
    ], "notes": [
        "يمكنك التحقق من سلامة أي دليل لاحقاً بزر Verify (يقارن التجزئة المخزَّنة بالحالية).",
    ], "shots": [("s01_cases_cases.png", "قضية حقيقية مستوردة في جدول القضايا مع الدليل المرتبط بها.")]},

    # ------------------------------------------------------------ hashing
    {"title": "2) التجزئة والتحقق من السلامة (Hashing)", "steps": [
        "صفحة <b>Hashing</b> ← حقل File ← اختر الملف ← زر <b>Compute</b>: يحسب MD5/SHA‑1/SHA‑256/SHA‑512 دفعة واحدة.",
        "للمقارنة: ضع الأصل في File A والمخرَج في File B ← زر <b>Compare</b>: يعرض MATCH أو MISMATCH مع الفرق في الحجم والاستنتاج.",
        "استخدمها بعد أي عملية إخفاء/حقن لتثبت أن الأصل لم يتغيَّر وأن المخرَج مختلف كما تتوقع.",
    ], "notes": ["التجزئة تُحفظ تلقائياً عند استيراد الأدلة، ويمكن تصديرها CSV."],
     "shots": [("s02_hashing_hashing.png", "حساب 4 تجزئات لملف حقيقي."),
               ("s03_hashing_hashing.png", "مقارنة ملف مع نفسه: MATCH.")]},

    # ------------------------------------------------------------ metadata
    {"title": "3) البيانات الوصفية (Metadata)", "steps": [
        "صفحة <b>Metadata</b> ← اختر ملفاً (صورة/فيديو) ← زر <b>Read</b>: يعرض الوسوم عبر exiftool (أو قارئ احتياطي إن غاب).",
        "للحقن: اختر ملفاً + اكتب وسوماً (مثل Artist/Comment) + مسار إخراج ← زر <b>Inject</b>: يكتب الوسوم في <b>نسخة</b> وليس الأصل.",
        "زر <b>Strip</b>: ينسخ الملف بدون الوسوم الحساسة (للمشاركة الآمنة).",
        "زر <b>Compare</b>: يعرض الفرق قبل/بعد (وسوم مضافة/محذوفة).",
    ], "notes": ["سطر Before/After SHA‑256 يثبت أن الأصل لم يُمَسّ بعد الحقن."],
     "shots": [("s04_metadata_metadata.png", "قراءة وسوم صورة عبر exiftool."),
               ("s05_metadata_metadata.png", "حقن وسمين في نسخة عمل؛ تجزئة الأصل لم تتغيَّر.")]},

    # ------------------------------------------------------------ forensics
    {"title": "4) الطب الشرعي للملفات (Forensics)", "steps": [
        "صفحة <b>Forensics</b> ← اختر ملفاً ← شغّل أي أداة منفردة: file / strings / entropy / binwalk / steghide --info / foremost / zsteg / ffprobe.",
        "زر <b>Triage</b> (الفرز الشامل): يشغّل كل الأدوات دفعة واحدة ويعرض ملخص المؤشرات.",
        "افهم النتائج كمؤشرات لا أدلة قاطعة — الأداة تصرّح بذلك في الواجهة.",
        "زر Carve (اختياري) يستخرج الملفات المضمَّنة عبر foremost/binwalk إلى مجلد عمل.",
    ], "notes": ["الأدوات غير المثبَّتة تظهر UNAVAILABLE بصدق ولا تُزيَّف نتائجها."],
     "shots": [("s06_forensics_forensics.png", "فرز شامل لملف: عدد المؤشرات وتفاصيل كل أداة.")]},

    # ------------------------------------------------------------ text
    {"title": "5) الإخفاء في النص (Text Steganography)", "steps": [
        "صفحة <b>Text</b> ← حمِّل أو اكتب «نص الغلاف» (Cover) في الصندوق الأيسر.",
        "اكتب الرسالة السرية في Secret والمفتاح في Key (≥4 أحرف).",
        "زر <b>Encode</b>: يبثّ الرسالة داخل الغلاف ويعرض النص المُخفى (Stego) مع السعة والاستغلال.",
        "للاستخراج: ضع نص Stego في الصندوق الأيمن (أو يُعبَّأ تلقائياً) ← زر <b>Decode</b> بنفس المفتاح.",
        "زر <b>Analyse</b> يفحص نصاً مشبوهاً ويعطي مؤشرات إحصائية (LSB bias / Chi‑sq).",
    ], "notes": ["المفتاح الخاطئ يعطي رسالة خاطئة/فشل تحقق — جرّب ذلك للتعلّم."],
     "shots": [("s07_text_text.png", "Encode: الرسالة بُثّت في الغلاف مع مؤشرات السعة."),
               ("s08_text_text.png", "Decode بنفس المفتاح: استرجاع الرسالة الأصلية.")]},

    # ------------------------------------------------------------ image
    {"title": "6) الإخفاء في الصور (Image Steganography)", "steps": [
        "صفحة <b>Image</b> ← اختر Carrier (صورة PNG للمحرّك الأصلي، أو JPEG/BMP لـ Steghide).",
        "اختر Secret (أي ملف) + Key + مسار Output.",
        "اختر المحرّك من القائمة: <b>native</b> (LSB أصلي) أو <b>steghide</b> أو <b>cyberhide</b> (مرجعي).",
        "زر <b>Hide</b> ← ثم <b>Extract</b> من ملف الـStego بنفس المفتاح لاسترجاع السر.",
        "زر <b>Analyse</b> يعطي تحليلاً إحصائياً للصورة (مقارنة مع مرجع إن وُجد).",
    ], "notes": ["Steghide لا يدعم PNG — استخدم JPEG/BMP وإلا ظهر UNSUPPORTED_FORMAT بصدق."],
     "shots": [("s09_image_image.png", "Native LSB hide في PNG."),
               ("s10_image_image.png", "Native LSB extract: استرجاع مطابق."),
               ("s11_image_image.png", "Steghide hide في JPEG (أداة خارجية حقيقية)."),
               ("s12_image_image.png", "Steghide extract: استرجاع مطابق.")]},

    # ------------------------------------------------------------ audio
    {"title": "7) الإخفاء في الصوت (Audio Steganography)", "steps": [
        "صفحة <b>Audio</b> ← اختر Carrier (WAV 16‑bit؛ زر Prepare يحوّل أي صيغة عبر ffmpeg).",
        "اختر التقنية من القائمة: <b>lsb</b> أو <b>phase</b> أو <b>spread</b>.",
        "أدخل Secret + Key + Output ← زر <b>Hide</b>؛ يعرض الكونسول الحجم وSNR وحالة التحقق.",
        "للاستخراج: ضع الـStego + نفس المفتاح ← زر <b>Extract</b>.",
        "زر <b>Tools</b> يعرض حالة الأدوات الخارجية (Audacity/DeepSound/Coagula) كـ EXTERNAL بصدق.",
    ], "notes": [
        "phase يحتاج حاملاً ≥15 ثانية؛ spread (DSSS أصلي) يحتاج حاملاً أطول (≈30 ث) لسعة كافية — كلاهما يعمل الآن فعلياً.",
        "أدوات الرسم (waveform/spectrogram) أسفل الصفحة للتحليل البصري.",
    ],
     "shots": [("s13_audio_audio.png", "LSB hide في WAV."),
               ("s14_audio_audio.png", "LSB extract مطابق."),
               ("s15_audio_audio.png", "Phase‑coding hide (حامل 16 ث)."),
               ("s16_audio_audio.png", "Phase extract مطابق."),
               ("s17_audio_audio.png", "Spread‑spectrum (DSSS) hide (حامل 30 ث)."),
               ("s18_audio_audio.png", "Spread extract (كشف أعمى) مطابق.")]},

    # ------------------------------------------------------------ video
    {"title": "8) الإخفاء في الفيديو (Video Steganography)", "steps": [
        "صفحة <b>Video</b> ← اختر Carrier (mp4) + Secret + Key + Output.",
        "اختر التقنية: <b>lsb</b> (يتطلب إخراجاً lossless مثل ‎.mkv — الأداة ترفض ‎.mp4 للإخراج وتشرح السبب) أو <b>container</b> (حاوية EOF مخصّصة) أو <b>spread</b>.",
        "زر <b>Hide</b> ← ثم <b>Extract</b> بنفس المفتاح؛ ولحاوية EOF استخدم <b>Detect</b> للكشف عن وجود الحاوية.",
        "الحاوية المخصّصة <b>ليست OpenPuff</b> ولا توافق معها — الواجهة تصرّح بذلك.",
    ], "notes": ["الناقل بعد الإخفاء يفتح ويعمل طبيعياً (الإخفاء بعد EOF أو في إطارات lossless)."],
     "shots": [("s19_video_video.png", "Video LSB hide إلى ‎.mkv."),
               ("s20_video_video.png", "Video LSB extract مطابق."),
               ("s21_video_video.png", "EOF‑container hide (إلحاق مشفَّر بعد EOF)."),
               ("s22_video_video.png", "Detect: اكتشاف الحاوية المخصّصة."),
               ("s23_video_video.png", "Container extract: استرجاع الملف الأصلي باسمه.")]},

    # ------------------------------------------------------------ network
    {"title": "9) الإخفاء في الشبكة (Network Steganography)", "steps": [
        "صفحة <b>Network</b> ← اكتب Payload ← زر <b>Preview</b>: يعرض خريطة حقن القيم في حقل IPv4 Identification (تصميمياً، للتعليم).",
        "زر <b>Analyse</b> + اختر ملف ‎.pcap: يفسّر الشذوذ الإحصائي ويعرضه كمؤشر لا دليل، مع شرح لماذا.",
        "<b>Send / Receive</b>: قناة UDP أساسية تعمل بلا root (غير سرية — للمقارنة التعليمية).",
        "قناة <b>IPv4‑ID السرية</b> تتطلب: تشغيل الأداة بـ <code>sudo</code> + تفعيل «Authorized laboratory mode» من Settings؛ والوجهة مقيّدة بـ loopback/RFC1918 فقط.",
    ], "notes": ["بدون root تظهر الحالة GATED/Permission denied بصدق — ليس عطلاً."],
     "shots": [("s24_network_network.png", "Encode preview: خريطة حقل IPv4‑ID."),
               ("s25_network_network.png", "تحليل pcap: 17 حزمة، ثقة High، مع تنويه «مؤشر لا دليل»."),
               ("s26_network_network.png", "Send+Receive على loopback: وصول فعلي للحمولة.")]},

    # ------------------------------------------------------------ malware
    {"title": "10) تحليل البرمجيات الخبيثة (Malware Analysis)", "steps": [
        "صفحة <b>Malware</b> ← اختر عيّنة (أرشيف/PE/نص…) ← زر <b>Analyse</b>.",
        "التحليل <b>ساكن فقط</b>: تجزئات، نوع الملف، سلاسل مريبة، إنتروبيا، مؤشرات IOC، انتحال أسماء، timestomping.",
        "النتيجة: درجة إرشادية + مستوى ثقة + تقييم نصي — دون تنفيذ العيّنة أبداً.",
        "استخدم <b>Simulate</b> لمشاهدة محاكاة تعليمية لسلوك ما (لا تنفيذ حقيقي).",
    ], "notes": ["التحليل الديناميكي/السandbox محجوب دائماً بتصميم أمني — هذا مقصود وليس نقصاً."],
     "shots": [("s27_malware_malware.png", "تحليل ساكن لأرشيف: درجة ومؤشرات وثقة، دون تنفيذ.")]},

    # ------------------------------------------------------------ reports/extraction
    {"title": "11) التقارير ومركز الاستخراج (Reports / Extraction)", "steps": [
        "صفحة <b>Reports</b> ← زر <b>Generate</b>: يبني تقرير القضية بثلاث صيغ (PDF/HTML/JSON) مع كل الأدلة والنتائج والتجزئات.",
        "الجدول يعرض الحجم وتجزئة كل تقرير؛ زر Open لفتحه.",
        "صفحة <b>Extraction Center</b>: تجمع النتائج/الملفات المستخرجة من كل العمليات في مكان واحد.",
        "صفحة <b>Investigation Logs</b>: سجل تدقيق كامل لكل إجراء (من/متى/ماذا/النتيجة) — دليلك على أن كل شيء حقيقي.",
    ], "notes": ["التقارير تُنشأ من قاعدة البيانات الفعلية — لا محتوى وهمي."],
     "shots": [("s28_reports_reports.png", "توليد PDF+HTML+JSON لقضية حقيقية."),
               ("s29_extraction_extraction.png", "مركز الاستخراج يجمع المخرجات.")]},

    # ------------------------------------------------------------ settings
    {"title": "12) الإعدادات وصحة الأدوات (Settings / Tool Health)", "steps": [
        "<b>Tool Health</b>: يعرض مصفوفة الأدوات (مثبّت/UNAVAILABLE/REFERENCE) بإصدارات حقيقية — راجعها أولاً عند أي مشكلة.",
        "<b>External Tools</b>: حالة الأدوات الخارجية وخيارات فتح الملفات بها.",
        "<b>Settings</b>: السمة، المحقِّق الافتراضي، «Authorized laboratory mode» للشبكة، ووضع القراءة‑فقط.",
    ], "notes": ["فعّل وضع المختبر المصرَّح فقط في بيئة معزولة مصرّح لك بها."],
     "shots": []},
]


def build() -> None:
    parts = ["""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>دليل استخدام StegoNexus — كل الخدمات</title>
<style>
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;font-family:'Segoe UI',Tahoma,system-ui,Arial,sans-serif;line-height:1.8;color:#1b1f24;background:#f6f7f9}
header{padding:26px 22px;background:#0d1b2a;color:#eaf2ff}
header h1{margin:0 0 8px;font-size:24px}
header p{margin:2px 0;color:#b9cbe0;font-size:14px}
.wrap{max-width:1000px;margin:0 auto;padding:18px}
section{background:#fff;border:1px solid #e2e6ea;border-radius:12px;margin:22px 0;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
h2{margin:0 0 10px;font-size:19px;color:#0d3b66;border-bottom:2px solid #0d1b2a;padding-bottom:6px}
ol{padding-right:22px;margin:8px 0}
li{margin:6px 0}
code{background:#eef1f4;padding:1px 6px;border-radius:5px;font-family:Consolas,Menlo,monospace;font-size:13px;direction:ltr;unicode-bidi:embed}
.note{background:#fff8e1;border:1px solid #f0d089;border-radius:8px;padding:8px 12px;font-size:13.5px;margin:10px 0}
figure{margin:14px 0 0}
figure img{width:100%;border:1px solid #dfe4e9;border-radius:8px;display:block}
figcaption{margin-top:6px;font-size:13.5px;color:#445;background:#f0f4f8;border-right:4px solid #2f6fb0;padding:6px 10px;border-radius:0 6px 6px 0}
@media (prefers-color-scheme:dark){body{background:#0f1418;color:#e6edf3}section{background:#161b20;border-color:#2a3138}header{background:#000}.note{background:#2a2410;border-color:#5a4a1f}code{background:#222a31}figcaption{background:#13202b;color:#bcd}}
</style></head><body>
<header><h1>دليل استخدام StegoNexus — شرح كل الخدمات</h1>
<p>كل شرح أدناه مرفق بلقطة شاشة حقيقية من التطبيق بعد تنفيذ العملية فعلياً (لا صور مولّدة).</p>
<p>القاعدة الذهبية: الأداة قراءة‑فقط — الأصل لا يتغيَّر أبداً، وكل إجراء مسجَّل في سجل التدقيق.</p></header>
<div class="wrap">"""]

    for sec in SECTIONS:
        parts.append(f"<section><h2>{html.escape(sec['title'])}</h2><ol>")
        for s in sec["steps"]:
            parts.append(f"<li>{s}</li>")
        parts.append("</ol>")
        for n in sec.get("notes", []):
            parts.append(f'<div class="note">⚠ {html.escape(n)}</div>')
        for fname, cap in sec.get("shots", []):
            parts.append(f"<figure><img src='{uri(fname)}' alt='{html.escape(cap)}'/>"
                         f"<figcaption>📷 {html.escape(cap)}</figcaption></figure>")
        parts.append("</section>")

    parts.append("</div></body></html>")
    OUT.write_text("".join(parts))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    build()
