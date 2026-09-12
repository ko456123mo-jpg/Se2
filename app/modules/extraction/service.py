"""Extraction Center service (project rule 54)."""
from __future__ import annotations

from app.core.constants import Status
from app.storage.database import get_db

TECHNIQUES = {
    "text_lsb_key": "Text LSB + Key",
    "image_steghide": "Image - Steghide",
    "image_lsb_native": "Image - native LSB",
    "audio_lsb": "Audio - LSB",
    "audio_phase_coding": "Audio - phase coding",
    "audio_spread_spectrum": "Audio - spread spectrum",
    "video_lsb": "Video - LSB (FFV1)",
    "video_container_eof": "Video - EOF container (custom)",
    "video_spread_spectrum": "Video - spread spectrum",
    "network_ipv4_id": "Network - IPv4 Identification",
    "network_udp": "Network - UDP payload (baseline)",
    "metadata_inject": "Metadata injection",
}


def list_operations(case_id: int | None = None, technique: str = "",
                    operation: str = "", status: str = "", limit: int = 500) -> list[dict]:
    rows = get_db().list_extractions(case_id, limit=limit)
    if technique:
        rows = [r for r in rows if r["technique"] == technique]
    if operation:
        rows = [r for r in rows if r["operation"] == operation]
    if status:
        rows = [r for r in rows if r["status"] == status]
    for row in rows:
        row["technique_label"] = TECHNIQUES.get(row["technique"], row["technique"])
    return rows


def summary(case_id: int | None = None) -> dict:
    rows = list_operations(case_id, limit=5000)
    by_technique: dict[str, int] = {}
    by_status: dict[str, int] = {}
    verified = 0
    for row in rows:
        by_technique[row["technique_label"]] = by_technique.get(row["technique_label"], 0) + 1
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        if row["verified"]:
            verified += 1
    return {"total": len(rows), "by_technique": by_technique, "by_status": by_status,
            "verified": verified,
            "success_rate": round(verified / len(rows), 4) if rows else 0.0}


def detail(operation_id: int) -> dict:
    from app.storage.database import _conn

    row = _conn().execute("SELECT * FROM extractions WHERE id=?",
                          (operation_id,)).fetchone()
    if not row:
        from app.core.exceptions import ValidationError

        raise ValidationError(f"Operation {operation_id} does not exist.")
    import json

    data = dict(row)
    for field in ("messages", "details"):
        try:
            data[field] = json.loads(data.get(field) or "[]")
        except json.JSONDecodeError:
            data[field] = []
    return data
