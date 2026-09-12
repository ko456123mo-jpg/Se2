"""Hashing & integrity service (project rule 19).

Algorithms: MD5, SHA-1, SHA-256, SHA-512 (all four are required by the project
specification).  SHA-256 is the primary integrity hash used for evidence and
before/after comparison.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from app.core.config import get_config
from app.core.constants import HASH_ALGORITHMS, PRIMARY_HASH
from app.core.logger import log_event
from app.core.models import HashResult
from app.core.security import validate_readable_file
from app.storage.database import get_db


def hash_file(path: Path, algorithms: tuple[str, ...] = HASH_ALGORITHMS,
              case_id: int | None = None, evidence_id: int | None = None) -> HashResult:
    """Compute the requested digests in a single streaming pass."""
    target = validate_readable_file(path)
    digesters = {name: hashlib.new(name) for name in algorithms}
    started = time.perf_counter()
    size = 0
    with open(target, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            for digester in digesters.values():
                digester.update(chunk)
    elapsed = (time.perf_counter() - started) * 1000
    result = HashResult(path=str(target), size=size,
                        hashes={name: d.hexdigest() for name, d in digesters.items()},
                        elapsed_ms=round(elapsed, 2))
    db = get_db()
    db.add_hash({"case_id": case_id, "evidence_id": evidence_id, "path": result.path,
                 "size": size, **result.hashes, "elapsed_ms": result.elapsed_ms})
    db.log_action(action="Hash Calculated", module="hashing", target=result.path,
                  case_id=case_id, evidence_id=evidence_id, result="OK",
                  hash_value=result.hashes.get(PRIMARY_HASH, ""))
    log_event("hashing", "hash_file", f"{target.name} sha256={result.sha256[:16]}...",
              case_id=case_id, evidence_id=evidence_id)
    return result


def hash_bytes(data: bytes, algorithms: tuple[str, ...] = HASH_ALGORITHMS) -> dict[str, str]:
    """Digests for in-memory data (used for payloads and reports)."""
    return {name: hashlib.new(name, data).hexdigest() for name in algorithms}


def compare(path_a: Path, path_b: Path) -> dict:
    """Full before/after comparison of two files."""
    a = hash_file(path_a)
    b = hash_file(path_b)
    rows = []
    identical = True
    for name in HASH_ALGORITHMS:
        match = a.hashes.get(name) == b.hashes.get(name)
        identical &= match
        rows.append({"algorithm": name, "a": a.hashes.get(name, ""),
                     "b": b.hashes.get(name, ""), "match": match})
    return {
        "file_a": a.path, "file_b": b.path, "size_a": a.size, "size_b": b.size,
        "size_delta": b.size - a.size, "rows": rows, "identical": identical,
        "primary_algorithm": PRIMARY_HASH,
        "conclusion": ("Files are byte-for-byte identical across all four algorithms."
                       if identical else
                       "Files differ. The difference may be caused by the intended "
                       "operation (embedding, metadata injection, re-encoding) - "
                       "interpret it against the operation log."),
    }


def verify(original: Path, candidate: Path) -> dict:
    """SHA-256 verification used after every generated artefact."""
    a = hash_file(original)
    b = hash_file(candidate)
    match = a.sha256 == b.sha256
    return {"original": a.path, "candidate": b.path, "algorithm": PRIMARY_HASH,
            "original_sha256": a.sha256, "candidate_sha256": b.sha256,
            "match": match,
            "assessment": ("Verified identical (SHA-256)." if match else
                           "NOT identical (SHA-256). The candidate is a different "
                           "artefact - record it as derived data.")}


def verify_against_hash(path: Path, expected_sha256: str) -> dict:
    """Check a file against a previously recorded SHA-256 value."""
    result = hash_file(path)
    expected = (expected_sha256 or "").strip().lower()
    match = result.sha256.lower() == expected
    return {"path": result.path, "expected": expected, "actual": result.sha256,
            "match": match,
            "assessment": "Integrity verified." if match else
                          "INTEGRITY FAILURE - the file no longer matches the "
                          "recorded hash."}


def export_hashes(results: list[HashResult], destination: Path, fmt: str = "csv") -> Path:
    """Export hash records (CSV or JSON) for a case file."""
    cfg = get_config()
    out = Path(destination)
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        import json

        out.write_text(json.dumps([r.to_row() for r in results], indent=2),
                       encoding="utf-8")
    else:
        lines = [",".join(["path", "size", *HASH_ALGORITHMS])]
        for result in results:
            lines.append(",".join([
                f'"{result.path}"', str(result.size),
                *[result.hashes.get(a, "") for a in HASH_ALGORITHMS]]))
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    get_db().log_action(action="Hash Exported", module="hashing", target=str(out),
                        result=f"{len(results)} records")
    log_event("hashing", "export", f"{len(results)} hash records -> {out}")
    return out
