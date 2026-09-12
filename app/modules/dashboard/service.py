"""Dashboard service - every number comes from the database (project rule 11)."""
from __future__ import annotations

import os
import platform
import sys

from app.core.config import get_config
from app.modules.extraction.service import summary as extraction_summary
from app.services.tool_health import health
from app.storage.database import get_db


def metrics() -> dict:
    return get_db().metrics()


def recent(limit: int = 5) -> dict:
    db = get_db()
    return {
        "cases": db.list_cases()[:limit],
        "analyses": db.list_analyses(limit=limit),
        "findings": db.list_findings()[:limit],
        "extractions": db.list_extractions(limit=limit),
        "logs": db.list_logs(limit=limit),
        "evidence": db.list_evidence()[:limit],
        "reports": db.list_reports(limit=limit),
    }


def tool_status() -> dict:
    summary = health.summary()
    return {"total": summary["total"], "available": summary["available"],
            "missing_required": summary["missing_required"],
            "rows": summary["rows"]}


def system_status() -> dict:
    cfg = get_config()
    import shutil

    disk = shutil.disk_usage(str(cfg.root))
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "workspace": str(cfg.root),
        "database": str(cfg.db_path),
        "database_size": cfg.db_path.stat().st_size if cfg.db_path.exists() else 0,
        "disk_free_mb": round(disk.free / 1024 / 1024, 1),
        "theme": cfg.theme,
        "investigator": cfg.investigator,
        "authorized_lab": cfg.network_authorized_lab,
        "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
    }


def dashboard() -> dict:
    """Everything the Dashboard screen renders."""
    data = metrics()
    data["recent"] = recent()
    data["tools"] = tool_status()
    data["system"] = system_status()
    data["extraction_summary"] = extraction_summary()
    return data


def chart_series() -> dict:
    """Data series for the dashboard charts (all derived from real rows)."""
    data = metrics()
    return {
        "analysis_distribution": data["analyses_by_kind"],
        "file_type_distribution": data["evidence_by_kind"],
        "detection_results": {"hidden_data_detected": data["hidden_data_detected"],
                              "extraction_operations": data["extraction_operations"],
                              "extraction_success": data["extraction_success"]},
        "severity_distribution": data["findings_by_severity"],
        "tool_usage": _tool_usage(),
        "case_activity": _case_activity(),
    }


def _tool_usage(limit: int = 500) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in get_db().list_tool_executions(limit=limit):
        counts[row["tool"]] = counts.get(row["tool"], 0) + 1
    return counts


def _case_activity(days: int = 14) -> list[dict]:
    from collections import Counter

    counts: Counter[str] = Counter()
    for row in get_db().list_logs(limit=5000):
        day = (row["ts"] or "")[:10]
        if day:
            counts[day] += 1
    ordered = sorted(counts.items())[-days:]
    return [{"day": day, "events": total} for day, total in ordered]
