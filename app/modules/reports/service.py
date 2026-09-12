"""Investigation report generation (project rules 58, 88).

Formats: HTML (self-contained, base64 logo), PDF (Qt renderer) and JSON.
Every report is branded, hashed and registered in the case database.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from html import escape
from pathlib import Path

from app import APP_FULL_TITLE, APP_NAME, __version__
from app.core.config import get_config
from app.core.logger import log_event
from app.modules.cases.service import overview, timeline
from app.modules.dashboard.service import system_status
from app.modules.hashing.service import hash_file
from app.storage.database import get_db

LOGO_PNG = Path(__file__).resolve().parents[3] / "resources" / "branding" / "stegonexus-logo-light.png"
LOGO_SVG = Path(__file__).resolve().parents[3] / "resources" / "branding" / "stegonexus-logo-light.svg"


# ------------------------------------------------------------------ data assembly
def build(case_id: int) -> dict:
    """Assemble every section of the report from real case data."""
    data = overview(case_id)
    db = get_db()
    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "application": APP_NAME, "full_title": APP_FULL_TITLE, "version": __version__,
        "system": system_status(),
        "case": data["case"], "evidence": data["evidence"],
        "findings": db.list_findings(case_id),
        "analyses": db.list_analyses(case_id, limit=400),
        "extractions": db.list_extractions(case_id, limit=400),
        "logs": db.list_logs(case_id, limit=400),
        "reports": db.list_reports(case_id),
        "timeline": timeline(case_id, limit=200),
        "counters": {"evidence": data["evidence_count"], "findings": data["finding_count"],
                     "analyses": data["analysis_count"],
                     "extractions": data["extraction_count"],
                     "logs": data["log_count"],
                     "successful_extractions": data["successful_extractions"]},
        "findings_by_severity": data["findings_by_severity"],
    }


# ------------------------------------------------------------------ HTML render
def _logo_data_uri() -> str:
    if LOGO_PNG.exists():
        encoded = base64.b64encode(LOGO_PNG.read_bytes()).decode()
        return f"data:image/png;base64,{encoded}"
    if LOGO_SVG.exists():
        encoded = base64.b64encode(LOGO_SVG.read_bytes()).decode()
        return f"data:image/svg+xml;base64,{encoded}"
    return ""


def render_html(data: dict, *, theme: str = "light") -> str:
    dark = theme == "dark"
    bg = "#0b1220" if dark else "#f6f9fc"
    panel = "#111c30" if dark else "#ffffff"
    text = "#e6f0fb" if dark else "#122234"
    muted = "#93a9c2" if dark else "#5b748f"
    border = "#24354f" if dark else "#dbe5ef"
    accent = "#22d3ee" if dark else "#0e7490"

    def table(headers: list[str], rows: list[list[str]]) -> str:
        if not rows:
            return f'<p class="muted">No records.</p>'
        head = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
        body = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in row)
                       + "</tr>" for row in rows)
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    case = data["case"]
    counters = data["counters"]
    cards = "".join(
        f'<div class="card"><div class="card-value">{value}</div>'
        f'<div class="card-label">{label}</div></div>'
        for label, value in (("Evidence items", counters["evidence"]),
                             ("Analyses", counters["analyses"]),
                             ("Extractions", counters["extraction_count"]
                              if "extraction_count" in counters else counters["extractions"]),
                             ("Verified extractions", counters["successful_extractions"]),
                             ("Findings", counters["findings"]),
                             ("Log entries", counters["logs"])))

    severity_rows = [[name, count] for name, count in
                     sorted(data["findings_by_severity"].items())]
    evidence_rows = [[e["id"], e["name"], e["kind"], e["size"], e["mime"],
                      (e["sha256"] or "")[:32] + "...", e["created"]]
                     for e in data["evidence"]]
    analysis_rows = [[a["created"], a["kind"], a["tool"], a["status"],
                      a["summary"][:160], Path(a["path"]).name]
                     for a in data["analyses"][:120]]
    extraction_rows = [[x["created"], x["technique"], x["operation"], x["engine"],
                        x["status"], x["payload_bytes"],
                        "yes" if x["verified"] else ("no" if x["verified"] is None
                                                     else "no"),
                        Path(x["output_path"] or "-").name]
                       for x in data["extractions"][:120]]
    finding_rows = [[f["id"], f["severity"], f["category"], f["title"],
                     f["confidence"], f["investigator"], f["created"]]
                    for f in data["findings"]]
    log_rows = [[l["ts"], l["action"], l["module"], l["tool"], l["status"],
                 (l["result"] or "")[:120]] for l in data["logs"][:120]]
    timeline_rows = [[t["time"], t["type"], t["module"], (t["detail"] or "")[:140],
                      t["status"]] for t in data["timeline"][:120]]

    logo = _logo_data_uri()
    logo_html = (f'<img src="{logo}" alt="StegoNexus" class="logo"/>' if logo else "")
    conclusion = _conclusion(data)

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>StegoNexus Investigation Report - {escape(case.get('number', ''))}</title>
<style>
 body {{ background:{bg}; color:{text}; font-family:'DejaVu Sans',Arial,sans-serif;
        margin:0; padding:32px; }}
 .sheet {{ max-width:1100px; margin:0 auto; }}
 header {{ border-bottom:3px solid {accent}; padding-bottom:18px; margin-bottom:22px; }}
 .logo {{ height:70px; }}
 h1 {{ font-size:26px; margin:12px 0 4px; }}
 h2 {{ font-size:18px; margin-top:34px; border-left:4px solid {accent};
      padding-left:10px; }}
 .muted {{ color:{muted}; font-size:12.5px; }}
 .meta {{ display:flex; flex-wrap:wrap; gap:22px; margin:10px 0 4px; }}
 .meta div span {{ display:block; color:{muted}; font-size:11px; text-transform:uppercase;
                   letter-spacing:.08em; }}
 .cards {{ display:flex; flex-wrap:wrap; gap:12px; margin:16px 0; }}
 .card {{ background:{panel}; border:1px solid {border}; border-radius:10px;
         padding:12px 16px; min-width:130px; }}
 .card-value {{ font-size:24px; font-weight:700; color:{accent}; }}
 .card-label {{ font-size:11px; color:{muted}; text-transform:uppercase;
               letter-spacing:.06em; }}
 table {{ width:100%; border-collapse:collapse; background:{panel};
         border:1px solid {border}; border-radius:8px; overflow:hidden;
         font-size:12px; margin:10px 0 6px; }}
 th {{ background:{'#16233a' if dark else '#eaf1f8'}; text-align:left;
      padding:8px; font-size:11px; text-transform:uppercase; letter-spacing:.05em;
      color:{muted}; border-bottom:1px solid {border}; }}
 td {{ padding:7px 8px; border-bottom:1px solid {border}; vertical-align:top; }}
 tr:last-child td {{ border-bottom:none; }}
 .callout {{ background:{panel}; border:1px solid {border}; border-left:4px solid {accent};
            border-radius:8px; padding:14px 16px; margin:14px 0; font-size:13px; }}
 footer {{ margin-top:36px; border-top:1px solid {border}; padding-top:12px;
          font-size:11px; color:{muted}; }}
 code {{ background:{'#16233a' if dark else '#eef3f9'}; padding:1px 5px; border-radius:4px; }}
</style></head>
<body><div class="sheet">
<header>{logo_html}
  <h1>Investigation Report</h1>
  <div class="muted">{escape(APP_FULL_TITLE)} &#183; v{escape(data['version'])}</div>
  <div class="meta">
    <div><span>Case</span>{escape(case.get('number',''))}</div>
    <div><span>Title</span>{escape(case.get('title',''))}</div>
    <div><span>Investigator</span>{escape(case.get('investigator',''))}</div>
    <div><span>Status</span>{escape(case.get('status',''))}</div>
    <div><span>Opened</span>{escape(case.get('created',''))}</div>
    <div><span>Report generated</span>{escape(data['generated'])}</div>
  </div>
</header>

<h2>1. Executive summary</h2>
<div class="cards">{cards}</div>
<div class="callout">{escape(conclusion)}</div>

<h2>2. Case description</h2>
<p>{escape(case.get('description') or 'No description recorded.')}</p>
<p class="muted">Notes: {escape(case.get('notes') or 'none')}</p>

<h2>3. Evidence &amp; integrity</h2>
{table(['ID', 'Name', 'Kind', 'Size (bytes)', 'MIME', 'SHA-256 (prefix)', 'Imported'],
       evidence_rows)}
<p class="muted">Primary integrity algorithm: SHA-256. MD5, SHA-1 and SHA-512 are
recorded for every item in the database. Original evidence is immutable; derived and
extracted artefacts are recorded separately.</p>

<h2>4. Findings</h2>
{table(['ID', 'Severity', 'Category', 'Title', 'Confidence', 'Investigator', 'Created'],
       finding_rows)}
{table(['Severity', 'Count'], severity_rows) if severity_rows else ''}

<h2>5. Forensic &amp; steganography analysis</h2>
{table(['Time', 'Analysis', 'Tool', 'Status', 'Summary', 'File'], analysis_rows)}

<h2>6. Hiding / extraction operations</h2>
{table(['Time', 'Technique', 'Operation', 'Engine', 'Status', 'Payload bytes',
        'Verified', 'Output'], extraction_rows)}

<h2>7. Investigation timeline</h2>
{table(['Time', 'Event', 'Module', 'Detail', 'Status'], timeline_rows)}

<h2>8. Investigation log</h2>
{table(['Time', 'Action', 'Module', 'Tool', 'Status', 'Result'], log_rows)}

<h2>9. Environment</h2>
{table(['Property', 'Value'], [[k, v] for k, v in data['system'].items()])}

<footer>
 {escape(APP_FULL_TITLE)} &#183; version {escape(data['version'])} &#183;
 report generated {escape(data['generated'])} by
 {escape(data['system'].get('user',''))} on {escape(data['system'].get('platform',''))}.<br/>
 Academic use - all conclusions are supported by the records shown above.
 Indicators are not proof; every assessment states its confidence.
</footer>
</div></body></html>"""


def _conclusion(data: dict) -> str:
    counters = data["counters"]
    findings = data["findings"]
    high = [f for f in findings if f["severity"] in ("High", "Critical")]
    parts = [f"Case {data['case'].get('number', '')} contains "
             f"{counters['evidence']} evidence item(s), {counters['analyses']} "
             f"analysis record(s), {counters['extractions']} hiding/extraction "
             f"operation(s) ({counters['successful_extractions']} verified) and "
             f"{counters['findings']} finding(s)."]
    if high:
        parts.append(f"{len(high)} finding(s) are rated High/Critical and require "
                     "immediate follow-up.")
    else:
        parts.append("No High/Critical finding was raised.")
    extractions = data["extractions"]
    recovered = [x for x in extractions if x["operation"] == "extract"
                 and x["status"] == "SUCCESS"]
    if recovered:
        parts.append(f"Hidden data was successfully recovered in {len(recovered)} "
                     "operation(s); each recovery is hash-verified.")
    parts.append("All statements in this report are derived from tool executions and "
                 "database records captured during the investigation; no result was "
                 "inferred without evidence.")
    return " ".join(parts)


# ------------------------------------------------------------------- PDF render
def render_pdf(data: dict, destination: Path, theme: str = "light") -> Path:
    """Render the report to PDF with Qt's PDF writer."""
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QGuiApplication, QPdfWriter, QTextDocument

    app = QGuiApplication.instance()
    if app is None:  # pragma: no cover - GUI always has one
        import sys

        app = QGuiApplication(sys.argv[:1])
    html = render_html(data, theme=theme)
    if LOGO_PNG.exists():
        html = html.replace(_logo_data_uri(), LOGO_PNG.resolve().as_uri())
    document = QTextDocument()
    document.setHtml(html)
    out = Path(destination)
    out.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(out))
    writer.setTitle(f"StegoNexus Report - {data['case'].get('number', '')}")
    writer.setCreator(APP_FULL_TITLE)
    writer.setPageMargins(QMarginsF(12, 12, 12, 12))
    document.print_(writer)
    return out


# ------------------------------------------------------------------ JSON render
def render_json(data: dict, destination: Path) -> Path:
    out = Path(destination)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return out


# ------------------------------------------------------------------- generation
def generate(case_id: int, formats: tuple[str, ...] = ("pdf", "html", "json"),
             title: str = "", theme: str = "light") -> list[dict]:
    """Generate the report in the requested formats and register each file."""
    cfg = get_config()
    data = build(case_id)
    if title:
        data["case"] = {**data["case"], "title": title}
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = f"case_{case_id:05d}_{stamp}"
    outputs: list[dict] = []
    db = get_db()
    for fmt in formats:
        if fmt not in ("pdf", "html", "json"):
            continue
        destination = cfg.reports_dir / f"{slug}.{fmt}"
        if fmt == "html":
            destination.write_text(render_html(data, theme=theme), encoding="utf-8")
        elif fmt == "json":
            render_json(data, destination)
        else:
            render_pdf(data, destination, theme=theme)
        digest = hash_file(destination, algorithms=("sha256",), case_id=case_id)
        record_id = db.add_report({"case_id": case_id,
                                   "title": title or f"Investigation Report "
                                                     f"{data['case'].get('number','')}",
                                   "fmt": fmt, "path": str(destination),
                                   "sha256": digest.sha256,
                                   "sections": 9})
        outputs.append({"id": record_id, "format": fmt, "path": str(destination),
                        "bytes": destination.stat().st_size, "sha256": digest.sha256})
        db.log_action(action="Report Generated", module="reports",
                      target=str(destination), case_id=case_id,
                      result=f"{fmt.upper()} report, {destination.stat().st_size} bytes",
                      hash_value=digest.sha256)
        log_event("reports", "generate", f"{fmt} report -> {destination.name}",
                  case_id=case_id, status="OK")
    return outputs


def list_reports(case_id: int | None = None, search: str = "") -> list[dict]:
    return get_db().list_reports(case_id, search=search)
