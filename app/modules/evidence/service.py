"""Evidence management service (project rules 53, 67-69).

Original evidence is **copied** into the case directory on import and treated as
immutable from then on: the application never writes to an original again.  Every
derived or extracted artefact is registered separately with its own hashes.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import get_config
from app.core.constants import EvidenceKind
from app.core.exceptions import ValidationError
from app.core.logger import log_event
from app.core.models import now_iso
from app.core.security import safe_filename, validate_readable_file
from app.modules.hashing.service import hash_file, verify_against_hash
from app.storage.database import get_db


def _case_dir(case_id: int, kind: str) -> Path:
    cfg = get_config()
    directory = cfg.cases_dir / f"case_{case_id:05d}" / kind
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _mime(path: Path) -> str:
    from app.services.tool_executor import executor

    if executor.is_available("file"):
        result = executor.run("file", ["--brief", "--mime-type", str(path)], timeout=30)
        if result.ok:
            return result.stdout.strip()
    import mimetypes

    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def import_file(case_id: int, source: Path, kind: str = EvidenceKind.ORIGINAL,
                notes: str = "", register_copy: bool = True,
                source_label: str = "local filesystem") -> dict:
    """Import evidence into a case, hashing it and (optionally) preserving a copy."""
    if kind not in EvidenceKind.ALL:
        raise ValidationError(f"Unknown evidence kind: {kind}")
    src = validate_readable_file(source)
    name = safe_filename(src.name, "evidence name")
    destination = src
    if register_copy and kind == EvidenceKind.ORIGINAL:
        destination = _case_dir(case_id, "original") / name
        if destination.exists():
            stem, suffix = Path(name).stem, Path(name).suffix
            destination = _case_dir(case_id, "original") / f"{stem}_{now_iso():%H%M%S}{suffix}"
        shutil.copy2(src, destination)
    hashes = hash_file(destination, case_id=case_id)
    record = get_db().add_evidence({
        "case_id": case_id, "name": name, "path": str(destination), "kind": kind,
        "source": source_label, "notes": notes, "size": hashes.size,
        "mime": _mime(destination), **hashes.hashes, "status": "imported"})
    db = get_db()
    db.log_action(action="Evidence Added", module="evidence", target=str(destination),
                  case_id=case_id, evidence_id=record["id"],
                  result=f"{kind}, {hashes.size} bytes", hash_value=hashes.sha256)
    log_event("evidence", "import", f"{name} ({kind}) sha256={hashes.sha256[:16]}...",
              case_id=case_id, evidence_id=record["id"])
    return record


def register_artifact(case_id: int, path: Path, kind: str = EvidenceKind.DERIVED,
                      notes: str = "", source_label: str = "stegonexus operation") -> dict:
    """Register a generated artefact (stego file, extraction, carve) as evidence."""
    if kind == EvidenceKind.ORIGINAL:
        raise ValidationError(
            "Generated artefacts must be registered as 'derived' or 'extracted' - "
            "only imported source files may be 'original'.")
    target = validate_readable_file(path)
    hashes = hash_file(target, case_id=case_id)
    record = get_db().add_evidence({
        "case_id": case_id, "name": safe_filename(target.name, "artifact name"),
        "path": str(target), "kind": kind, "source": source_label, "notes": notes,
        "size": hashes.size, "mime": _mime(target), **hashes.hashes,
        "status": "generated"})
    get_db().log_action(action="Artifact Registered", module="evidence",
                        target=str(target), case_id=case_id,
                        evidence_id=record["id"], result=f"{kind}, {hashes.size} bytes",
                        hash_value=hashes.sha256)
    return record


def list_evidence(case_id: int | None = None, search: str = "") -> list[dict]:
    return get_db().list_evidence(case_id, search=search)


def get(evidence_id: int) -> dict:
    record = get_db().get_evidence(evidence_id)
    if not record:
        raise ValidationError(f"Evidence {evidence_id} does not exist.")
    return record


def update(evidence_id: int, **fields) -> dict:
    record = get_db().update_evidence(evidence_id, **fields)
    if not record:
        raise ValidationError(f"Evidence {evidence_id} does not exist.")
    get_db().log_action(action="Evidence Updated", module="evidence",
                        target=record["path"], case_id=record["case_id"],
                        evidence_id=evidence_id, result=", ".join(sorted(fields)))
    return record


def working_copy(evidence_id: int, destination: Path | None = None) -> dict:
    """Create a mutable working copy so originals stay untouched."""
    record = get(evidence_id)
    src = Path(record["path"])
    if not src.exists():
        raise ValidationError(f"Evidence file is missing: {src}")
    target = Path(destination) if destination else _case_dir(
        record["case_id"], "working") / f"work_{src.name}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    hashes = hash_file(target, case_id=record["case_id"])
    copy_record = register_artifact(record["case_id"], target, EvidenceKind.WORKING_COPY,
                                    notes=f"working copy of evidence #{evidence_id}",
                                    source_label="evidence working copy")
    return {"original": record, "working_copy": copy_record, "path": str(target),
            "sha256": hashes.sha256,
            "note": "Original evidence remains immutable; work on this copy."}


def verify_integrity(evidence_id: int) -> dict:
    """Re-hash an evidence item and compare with the recorded value."""
    record = get(evidence_id)
    path = Path(record["path"])
    if not path.exists():
        return {"evidence_id": evidence_id, "path": str(path), "match": False,
                "assessment": "EVIDENCE MISSING - the file is no longer at the "
                              "recorded path."}
    result = verify_against_hash(path, record.get("sha256", ""))
    get_db().log_action(action="Integrity Verified", module="evidence",
                        target=record["path"], case_id=record["case_id"],
                        evidence_id=evidence_id, status="OK" if result["match"]
                        else "MISMATCH", result=result["assessment"],
                        hash_value=result["actual"])
    return {**result, "evidence_id": evidence_id}


def delete_record(evidence_id: int) -> None:
    """Remove the database record (files are never deleted by the application)."""
    record = get(evidence_id)
    get_db().log_action(action="Evidence Record Deleted", module="evidence",
                        target=record["path"], case_id=record["case_id"],
                        evidence_id=evidence_id,
                        result="record removed; file left on disk")
    from app.storage.database import _conn, _write_lock

    with _write_lock:
        _conn().execute("DELETE FROM evidence WHERE id=?", (evidence_id,))
