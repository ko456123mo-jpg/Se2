"""Investigation log service (project rule 57)."""
from __future__ import annotations

import csv
from pathlib import Path

from app.core.config import get_config
from app.core.logger import export_log
from app.storage.database import get_db

ACTIONS = ["Case Created", "Evidence Added", "Hash Calculated", "Metadata Read",
           "Metadata Modified", "Forensic Tool Executed", "Steganography Operation",
           "Extraction", "Finding Created", "Report Generated"]


def list_logs(case_id: int | None = None, search: str = "", status: str = "",
              limit: int = 500) -> list[dict]:
    return get_db().list_logs(case_id, search=search, status=status, limit=limit)


def search(term: str, case_id: int | None = None, limit: int = 500) -> list[dict]:
    return get_db().list_logs(case_id, search=term, limit=limit)


def export_csv(destination: Path, case_id: int | None = None, limit: int = 5000) -> dict:
    rows = list_logs(case_id, limit=limit)
    out = Path(destination)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["ts", "user", "action", "module", "target", "case_id", "evidence_id",
              "tool", "result", "status", "hash"]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    get_db().log_action(action="Log Exported", module="logs", target=str(out),
                        case_id=case_id, result=f"{len(rows)} rows")
    return {"path": str(out), "rows": len(rows)}


def export_application_log(destination: Path, last_n: int = 5000) -> dict:
    """Export the structured JSON application log (rule 85)."""
    out = export_log(Path(destination), last_n=last_n)
    return {"path": str(out), "lines": len(out.read_text().splitlines())
            if out.exists() else 0}


def summary(case_id: int | None = None, limit: int = 2000) -> dict:
    rows = list_logs(case_id, limit=limit)
    by_action: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for row in rows:
        key = row["action"].split(" (")[0]
        by_action[key] = by_action.get(key, 0) + 1
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    return {"total": len(rows), "by_action": by_action, "by_status": by_status,
            "first": rows[-1]["ts"] if rows else "", "last": rows[0]["ts"] if rows else ""}
