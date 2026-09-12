"""Findings management service (project rule 55)."""
from __future__ import annotations

from app.core.config import get_config
from app.core.constants import Severity
from app.core.exceptions import ValidationError
from app.core.logger import log_event
from app.core.security import validate_non_empty
from app.storage.database import get_db

CATEGORIES = ["Metadata", "Steganography", "Forensics", "Hashing", "Network",
              "Malware", "Integrity", "Procedural"]


def create(case_id: int, category: str, severity: str, title: str,
           description: str = "", indicator: str = "", evidence_ref: str = "",
           confidence: str = "Medium", investigator: str = "",
           evidence_id: int | None = None) -> dict:
    title = validate_non_empty(title, "Finding title")
    if severity not in Severity.ALL:
        raise ValidationError(f"Severity must be one of {', '.join(Severity.ALL)}.")
    if confidence not in ("Low", "Medium", "High"):
        raise ValidationError("Confidence must be Low, Medium or High.")
    category = validate_non_empty(category, "Category")
    record_id = get_db().add_finding({
        "case_id": case_id, "evidence_id": evidence_id, "category": category,
        "severity": severity, "title": title, "description": description,
        "indicator": indicator, "evidence_ref": evidence_ref, "confidence": confidence,
        "investigator": investigator or get_config().investigator})
    get_db().log_action(action="Finding Created", module="findings", target=title,
                        case_id=case_id, evidence_id=evidence_id,
                        result=f"{severity} / {category} / confidence {confidence}")
    log_event("findings", "create", f"{severity}: {title}", case_id=case_id)
    return get_db().list_findings(case_id)[0] if record_id else {}


def list_findings(case_id: int | None = None, severity: str = "",
                  search: str = "") -> list[dict]:
    return get_db().list_findings(case_id, severity=severity or None, search=search)


def delete(finding_id: int) -> None:
    get_db().log_action(action="Finding Deleted", module="findings",
                        target=f"#{finding_id}")
    get_db().delete_finding(finding_id)


def by_severity(case_id: int | None = None) -> dict[str, int]:
    counts = {name: 0 for name in Severity.ALL}
    for finding in list_findings(case_id):
        counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
    return counts


def from_analysis(case_id: int, analysis: dict, evidence_id: int | None = None) -> dict:
    """Create a finding directly from an analysis result (one click)."""
    severity = Severity.MEDIUM
    indicators = analysis.get("indicators") or []
    if any("Steghide reports embedded data" in i for i in indicators):
        severity = Severity.HIGH
    if analysis.get("heuristic_score", 0) >= 50:
        severity = Severity.HIGH
    if analysis.get("kind") == "entropy" and analysis.get("entropy", 0) >= 7.9:
        severity = Severity.LOW
    return create(case_id, category="Forensics", severity=severity,
                  title=f"{analysis.get('kind', 'analysis')} indicator on "
                        f"{Path_basename(analysis.get('path', ''))}",
                  description=(analysis.get("summary") or "") + "\n"
                              + "\n".join(f"- {i}" for i in indicators),
                  indicator="; ".join(indicators)[:500],
                  evidence_ref=analysis.get("path", ""), evidence_id=evidence_id,
                  confidence="Medium")


def Path_basename(path: str) -> str:
    from pathlib import Path

    return Path(path).name if path else "unknown"
