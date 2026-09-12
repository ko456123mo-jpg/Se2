"""Case management service (project rule 56)."""
from __future__ import annotations

from app.core.config import get_config
from app.core.constants import CaseState
from app.core.exceptions import ValidationError
from app.core.logger import log_event
from app.core.models import now_iso
from app.core.security import safe_filename, validate_non_empty
from app.storage.database import get_db


def create(title: str, description: str = "", investigator: str = "",
           tags: str = "", number: str = "") -> dict:
    title = validate_non_empty(title, "Case title")
    investigator = investigator or get_config().investigator
    case = get_db().create_case(title=title, description=description,
                                investigator=investigator, tags=tags,
                                number=number or None)
    get_db().log_action(action="Case Created", module="cases", target=case["title"],
                        case_id=case["id"], user=investigator,
                        result=f"case {case['number']}")
    log_event("cases", "create", f"case {case['number']} '{case['title']}'",
              case_id=case["id"])
    return case


def open_case(case_id: int) -> dict:
    case = get_db().get_case(case_id)
    if not case:
        raise ValidationError(f"Case {case_id} does not exist.")
    return case


def list_cases(status: str = "", search: str = "") -> list[dict]:
    return get_db().list_cases(status=status or None, search=search)


def update(case_id: int, **fields) -> dict:
    case = get_db().update_case(case_id, **fields)
    if not case:
        raise ValidationError(f"Case {case_id} does not exist.")
    get_db().log_action(action="Case Updated", module="cases", target=case["title"],
                        case_id=case_id, result=", ".join(sorted(fields)))
    return case


def close(case_id: int) -> dict:
    case = update(case_id, status=CaseState.CLOSED, closed=now_iso())
    get_db().log_action(action="Case Closed", module="cases", target=case["title"],
                        case_id=case_id)
    return case


def reopen(case_id: int) -> dict:
    case = update(case_id, status=CaseState.OPEN, closed=None)
    get_db().log_action(action="Case Reopened", module="cases", target=case["title"],
                        case_id=case_id)
    return case


def archive(case_id: int) -> dict:
    case = update(case_id, status=CaseState.ARCHIVED)
    get_db().log_action(action="Case Archived", module="cases", target=case["title"],
                        case_id=case_id)
    return case


def add_note(case_id: int, note: str) -> dict:
    case = open_case(case_id)
    text = validate_non_empty(note, "Note")
    merged = (case.get("notes") or "") + f"\n[{now_iso()}] {text}"
    updated = update(case_id, notes=merged.strip())
    get_db().log_action(action="Note Added", module="cases", target=case["title"],
                        case_id=case_id, result=text[:200])
    return updated


def overview(case_id: int) -> dict:
    """Everything the Overview tab needs, from real queries."""
    db = get_db()
    case = open_case(case_id)
    evidence = db.list_evidence(case_id)
    findings = db.list_findings(case_id)
    analyses = db.list_analyses(case_id, limit=1000)
    extractions = db.list_extractions(case_id, limit=1000)
    logs = db.list_logs(case_id, limit=1000)
    reports = db.list_reports(case_id)
    severity: dict[str, int] = {}
    for finding in findings:
        severity[finding["severity"]] = severity.get(finding["severity"], 0) + 1
    return {
        "case": case, "evidence_count": len(evidence), "evidence": evidence,
        "finding_count": len(findings), "findings_by_severity": severity,
        "analysis_count": len(analyses), "extraction_count": len(extractions),
        "successful_extractions": sum(1 for e in extractions if e["status"] == "SUCCESS"),
        "log_count": len(logs), "report_count": len(reports),
        "timeline": timeline(case_id),
    }


def timeline(case_id: int, limit: int = 500) -> list[dict]:
    """Merged, chronological investigation timeline."""
    db = get_db()
    events: list[dict] = []
    for row in db.list_logs(case_id, limit=limit):
        events.append({"time": row["ts"], "type": row["action"],
                       "detail": row["result"] or row["target"],
                       "module": row["module"], "status": row["status"]})
    for row in db.list_extractions(case_id, limit=limit):
        events.append({"time": row["created"], "type": f"{row['technique']} "
                                                      f"({row['operation']})",
                       "detail": row["output_path"] or row["input_path"],
                       "module": row["engine"], "status": row["status"]})
    for row in db.list_analyses(case_id, limit=limit):
        events.append({"time": row["created"], "type": row["kind"],
                       "detail": row["summary"], "module": row["tool"],
                       "status": row["status"]})
    events.sort(key=lambda item: item["time"], reverse=True)
    return events


def delete(case_id: int) -> None:
    case = open_case(case_id)
    get_db().delete_case(case_id)
    log_event("cases", "delete", f"case {case['number']} deleted", case_id=case_id)


def export_case_bundle(case_id: int, destination) -> dict:
    """Write a JSON bundle of the whole case (evidence stays in place)."""
    import json
    from pathlib import Path

    data = overview(case_id)
    out = Path(destination)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    get_db().log_action(action="Case Exported", module="cases", target=str(out),
                        case_id=case_id)
    return {"path": str(out), "bytes": out.stat().st_size}
