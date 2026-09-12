"""SQLite data access layer.

Single-file local database (``data/stegonexus.db``).  A process-wide instance
plus a re-entrant lock keep the GUI threads and the worker threads safe; the
connection is opened per thread because SQLite connections are not shareable.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from app.core.config import get_config
from app.core.exceptions import DatabaseError
from app.core.models import now_iso

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_VERSION = "1"

_local = threading.local()
_write_lock = threading.RLock()
_DB_PATH: Path | None = None


def _conn() -> sqlite3.Connection:
    if _DB_PATH is None:  # pragma: no cover - defensive
        raise DatabaseError("Database not initialised. Call Database() first.")
    conn = getattr(_local, "conn", None)
    if conn is None:
        try:
            conn = sqlite3.connect(str(_DB_PATH), timeout=30, isolation_level=None)
        except sqlite3.Error as exc:  # pragma: no cover
            raise DatabaseError(f"Cannot open database: {exc}") from exc
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        _local.conn = conn
    return conn


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


class Database:
    """Thin, typed wrapper around the SQLite schema."""

    def __init__(self, path: Path | None = None):
        global _DB_PATH
        if path is None:
            path = get_config().db_path
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        _DB_PATH = path
        self.path = path
        _local.conn = None  # reset thread-local for a new path
        self.init_schema()

    # ------------------------------------------------------------------ schema
    def init_schema(self) -> None:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with _write_lock:
            try:
                _conn().executescript(sql)
                _conn().execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
                    ("schema_version", SCHEMA_VERSION))
            except sqlite3.Error as exc:
                raise DatabaseError(f"Schema initialisation failed: {exc}") from exc

    def close(self) -> None:
        conn = getattr(_local, "conn", None)
        if conn is not None:
            conn.close()
            _local.conn = None

    # ------------------------------------------------------------------- cases
    def create_case(self, *, title: str, description: str = "",
                    investigator: str = "", notes: str = "", tags: str = "",
                    number: str | None = None) -> dict:
        ts = now_iso()
        number = number or f"SNX-{datetime.now():%Y%m%d-%H%M%S}"
        with _write_lock:
            cur = _conn().execute(
                "INSERT INTO cases(number, title, description, investigator, "
                "status, notes, tags, created) VALUES(?,?,?,?,?,?,?,?)",
                (number, title, description, investigator, "Open", notes, tags, ts))
            return self.get_case(cur.lastrowid)  # type: ignore[arg-type]

    def get_case(self, case_id: int) -> dict | None:
        row = _conn().execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        return dict(row) if row else None

    def list_cases(self, status: str | None = None, search: str = "") -> list[dict]:
        sql = ("SELECT c.*, (SELECT COUNT(*) FROM evidence e WHERE e.case_id=c.id) AS evidence_count, "
               "(SELECT COUNT(*) FROM findings f WHERE f.case_id=c.id) AS finding_count "
               "FROM cases c")
        where, args = [], []
        if status:
            where.append("c.status=?")
            args.append(status)
        if search:
            where.append("(c.title LIKE ? OR c.number LIKE ? OR c.investigator LIKE ? OR c.tags LIKE ?)")
            like = f"%{search}%"
            args += [like] * 4
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY c.id DESC"
        return rows_to_dicts(_conn().execute(sql, args).fetchall())

    def update_case(self, case_id: int, **fields: Any) -> dict | None:
        allowed = {"title", "description", "investigator", "status", "notes", "tags", "closed"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if sets:
            assignments = ", ".join(f"{k}=?" for k in sets)
            with _write_lock:
                _conn().execute(f"UPDATE cases SET {assignments} WHERE id=?",
                                (*sets.values(), case_id))
        return self.get_case(case_id)

    def delete_case(self, case_id: int) -> None:
        with _write_lock:
            _conn().execute("DELETE FROM cases WHERE id=?", (case_id,))

    # ---------------------------------------------------------------- evidence
    def add_evidence(self, evidence: dict) -> dict:
        with _write_lock:
            cur = _conn().execute(
                "INSERT INTO evidence(case_id, name, path, kind, source, notes, size, "
                "mime, md5, sha1, sha256, sha512, status, created) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (evidence["case_id"], evidence["name"], evidence["path"],
                 evidence.get("kind", "original"), evidence.get("source", ""),
                 evidence.get("notes", ""), evidence.get("size", 0),
                 evidence.get("mime", ""), evidence.get("md5", ""),
                 evidence.get("sha1", ""), evidence.get("sha256", ""),
                 evidence.get("sha512", ""), evidence.get("status", "imported"),
                 evidence.get("created") or now_iso()))
        return self.get_evidence(cur.lastrowid)  # type: ignore[arg-type]

    def get_evidence(self, evidence_id: int) -> dict | None:
        row = _conn().execute("SELECT * FROM evidence WHERE id=?", (evidence_id,)).fetchone()
        return dict(row) if row else None

    def list_evidence(self, case_id: int | None = None, search: str = "") -> list[dict]:
        sql = "SELECT * FROM evidence"
        where, args = [], []
        if case_id is not None:
            where.append("case_id=?")
            args.append(case_id)
        if search:
            where.append("(name LIKE ? OR path LIKE ? OR sha256 LIKE ?)")
            like = f"%{search}%"
            args += [like] * 3
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC"
        return rows_to_dicts(_conn().execute(sql, args).fetchall())

    def update_evidence(self, evidence_id: int, **fields: Any) -> dict | None:
        allowed = {"name", "path", "kind", "source", "notes", "size", "mime",
                   "md5", "sha1", "sha256", "sha512", "status"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if sets:
            assignments = ", ".join(f"{k}=?" for k in sets)
            with _write_lock:
                _conn().execute(f"UPDATE evidence SET {assignments} WHERE id=?",
                                (*sets.values(), evidence_id))
        return self.get_evidence(evidence_id)

    # ------------------------------------------------------------------ hashes
    def add_hash(self, record: dict) -> int:
        with _write_lock:
            cur = _conn().execute(
                "INSERT INTO hashes(case_id, evidence_id, path, size, md5, sha1, "
                "sha256, sha512, elapsed_ms, created) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (record.get("case_id"), record.get("evidence_id"), record["path"],
                 record.get("size", 0), record.get("md5", ""), record.get("sha1", ""),
                 record.get("sha256", ""), record.get("sha512", ""),
                 record.get("elapsed_ms", 0), record.get("created") or now_iso()))
        return cur.lastrowid  # type: ignore[return-value]

    def list_hashes(self, case_id: int | None = None, limit: int = 200) -> list[dict]:
        if case_id is None:
            rows = _conn().execute(
                "SELECT * FROM hashes ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = _conn().execute(
                "SELECT * FROM hashes WHERE case_id=? ORDER BY id DESC LIMIT ?",
                (case_id, limit)).fetchall()
        return rows_to_dicts(rows)

    # ---------------------------------------------------------------- analyses
    def add_analysis(self, record: dict) -> int:
        payload = record.get("payload", {})
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False, default=str)
        with _write_lock:
            cur = _conn().execute(
                "INSERT INTO analyses(case_id, evidence_id, kind, path, tool, status, "
                "summary, payload, elapsed_ms, created) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (record.get("case_id"), record.get("evidence_id"), record["kind"],
                 record["path"], record.get("tool", ""), record.get("status", ""),
                 record.get("summary", ""), payload, record.get("elapsed_ms", 0),
                 record.get("created") or now_iso()))
        return cur.lastrowid  # type: ignore[return-value]

    def list_analyses(self, case_id: int | None = None, kind: str | None = None,
                      limit: int = 200) -> list[dict]:
        sql = "SELECT * FROM analyses"
        where, args = [], []
        if case_id is not None:
            where.append("case_id=?")
            args.append(case_id)
        if kind:
            where.append("kind=?")
            args.append(kind)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return rows_to_dicts(_conn().execute(sql, args).fetchall())

    # ---------------------------------------------------------------- metadata
    def add_metadata_snapshot(self, record: dict) -> int:
        entries = record.get("entries", [])
        if not isinstance(entries, str):
            entries = json.dumps(entries, ensure_ascii=False, default=str)
        hashes = record.get("hashes", {})
        if not isinstance(hashes, str):
            hashes = json.dumps(hashes, ensure_ascii=False)
        with _write_lock:
            cur = _conn().execute(
                "INSERT INTO metadata_snapshots(case_id, evidence_id, path, source, "
                "available, entries, hashes, error, created) VALUES(?,?,?,?,?,?,?,?,?)",
                (record.get("case_id"), record.get("evidence_id"), record["path"],
                 record.get("source", ""), int(record.get("available", 1)), entries,
                 hashes, record.get("error", ""), record.get("created") or now_iso()))
        return cur.lastrowid  # type: ignore[return-value]

    # ------------------------------------------------------------- extractions
    def add_extraction(self, record: dict) -> int:
        messages = record.get("messages", [])
        if not isinstance(messages, str):
            messages = json.dumps(messages, ensure_ascii=False, default=str)
        details = record.get("details", {})
        if not isinstance(details, str):
            details = json.dumps(details, ensure_ascii=False, default=str)
        with _write_lock:
            cur = _conn().execute(
                "INSERT INTO extractions(case_id, evidence_id, technique, operation, "
                "engine, status_label, status, input_path, output_path, payload_bytes, "
                "capacity_bytes, input_hash, output_hash, verified, error, messages, "
                "details, elapsed_ms, created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (record.get("case_id"), record.get("evidence_id"), record["technique"],
                 record["operation"], record.get("engine", ""),
                 record.get("status_label", ""), record.get("status", ""),
                 record.get("input_path", ""), record.get("output_path", ""),
                 record.get("payload_bytes", 0), record.get("capacity_bytes", 0),
                 record.get("input_hash", ""), record.get("output_hash", ""),
                 record.get("verified"), record.get("error", ""), messages, details,
                 record.get("elapsed_ms", 0), record.get("created") or now_iso()))
        return cur.lastrowid  # type: ignore[return-value]

    def list_extractions(self, case_id: int | None = None, limit: int = 200) -> list[dict]:
        if case_id is None:
            rows = _conn().execute(
                "SELECT * FROM extractions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = _conn().execute(
                "SELECT * FROM extractions WHERE case_id=? ORDER BY id DESC LIMIT ?",
                (case_id, limit)).fetchall()
        return rows_to_dicts(rows)

    # ---------------------------------------------------------------- findings
    def add_finding(self, finding: dict) -> int:
        with _write_lock:
            cur = _conn().execute(
                "INSERT INTO findings(case_id, evidence_id, category, severity, title, "
                "description, indicator, evidence_ref, confidence, investigator, created) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (finding["case_id"], finding.get("evidence_id"), finding["category"],
                 finding["severity"], finding["title"], finding.get("description", ""),
                 finding.get("indicator", ""), finding.get("evidence_ref", ""),
                 finding.get("confidence", "Medium"), finding.get("investigator", ""),
                 finding.get("created") or now_iso()))
        return cur.lastrowid  # type: ignore[return-value]

    def list_findings(self, case_id: int | None = None, severity: str | None = None,
                      search: str = "") -> list[dict]:
        sql = "SELECT * FROM findings"
        where, args = [], []
        if case_id is not None:
            where.append("case_id=?")
            args.append(case_id)
        if severity:
            where.append("severity=?")
            args.append(severity)
        if search:
            where.append("(title LIKE ? OR description LIKE ? OR indicator LIKE ? OR category LIKE ?)")
            like = f"%{search}%"
            args += [like] * 4
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC"
        return rows_to_dicts(_conn().execute(sql, args).fetchall())

    def delete_finding(self, finding_id: int) -> None:
        with _write_lock:
            _conn().execute("DELETE FROM findings WHERE id=?", (finding_id,))

    # -------------------------------------------------------------------- logs
    def log_action(self, *, action: str, module: str = "", target: str = "",
                   user: str = "", case_id: int | None = None,
                   evidence_id: int | None = None, tool: str = "",
                   result: str = "", status: str = "OK", hash_value: str = "") -> int:
        with _write_lock:
            cur = _conn().execute(
                "INSERT INTO investigation_logs(ts, user, action, module, target, "
                "case_id, evidence_id, tool, result, status, hash) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (now_iso(), user, action, module, target, case_id, evidence_id,
                 tool, result[:2000], status, hash_value))
        return cur.lastrowid  # type: ignore[return-value]

    def list_logs(self, case_id: int | None = None, search: str = "",
                  status: str = "", limit: int = 500) -> list[dict]:
        sql = "SELECT * FROM investigation_logs"
        where, args = [], []
        if case_id is not None:
            where.append("case_id=?")
            args.append(case_id)
        if status:
            where.append("status=?")
            args.append(status)
        if search:
            where.append("(action LIKE ? OR module LIKE ? OR target LIKE ? OR result LIKE ? OR tool LIKE ?)")
            like = f"%{search}%"
            args += [like] * 5
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return rows_to_dicts(_conn().execute(sql, args).fetchall())

    # --------------------------------------------------------- tool executions
    def record_tool_execution(self, result: dict) -> int:
        argv = result.get("argv", [])
        if not isinstance(argv, str):
            argv = json.dumps(argv, ensure_ascii=False)
        with _write_lock:
            cur = _conn().execute(
                "INSERT INTO tool_executions(tool, argv, available, returncode, status, "
                "stdout_len, stderr_len, stderr_head, timed_out, elapsed_ms, case_id, created) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (result.get("tool", ""), argv, int(result.get("available", 0)),
                 result.get("returncode", 0), result.get("status", ""),
                 result.get("stdout_len", 0), result.get("stderr_len", 0),
                 result.get("stderr_head", "")[:500], int(result.get("timed_out", 0)),
                 result.get("elapsed_ms", 0), result.get("case_id"),
                 result.get("created") or now_iso()))
        return cur.lastrowid  # type: ignore[return-value]

    def list_tool_executions(self, limit: int = 200) -> list[dict]:
        return rows_to_dicts(_conn().execute(
            "SELECT * FROM tool_executions ORDER BY id DESC LIMIT ?", (limit,)).fetchall())

    # ----------------------------------------------------------------- reports
    def add_report(self, record: dict) -> int:
        with _write_lock:
            cur = _conn().execute(
                "INSERT INTO reports(case_id, title, fmt, path, sha256, sections, created) "
                "VALUES(?,?,?,?,?,?,?)",
                (record.get("case_id"), record["title"], record["fmt"], record["path"],
                 record.get("sha256", ""), record.get("sections", 0),
                 record.get("created") or now_iso()))
        return cur.lastrowid  # type: ignore[return-value]

    def list_reports(self, case_id: int | None = None, search: str = "",
                     limit: int = 200) -> list[dict]:
        sql = "SELECT * FROM reports"
        where, args = [], []
        if case_id is not None:
            where.append("case_id=?")
            args.append(case_id)
        if search:
            where.append("(title LIKE ? OR path LIKE ? OR fmt LIKE ?)")
            like = f"%{search}%"
            args += [like] * 3
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return rows_to_dicts(_conn().execute(sql, args).fetchall())

    # ------------------------------------------------------------- dashboard
    def metrics(self) -> dict[str, Any]:
        """All dashboard figures come from real queries - never hard-coded."""
        q = lambda sql, *a: _conn().execute(sql, a).fetchone()[0]  # noqa: E731
        sev = {r["severity"]: r["n"] for r in _conn().execute(
            "SELECT severity, COUNT(*) n FROM findings GROUP BY severity")}
        kinds = {r["kind"]: r["n"] for r in _conn().execute(
            "SELECT kind, COUNT(*) n FROM analyses GROUP BY kind")}
        techniques = {r["technique"]: r["n"] for r in _conn().execute(
            "SELECT technique, COUNT(*) n FROM extractions GROUP BY technique")}
        kinds_evidence = {r["kind"]: r["n"] for r in _conn().execute(
            "SELECT kind, COUNT(*) n FROM evidence GROUP BY kind")}
        detected = q("SELECT COUNT(*) FROM extractions WHERE status='SUCCESS' "
                     "AND operation='extract'")
        return {
            "cases": q("SELECT COUNT(*) FROM cases"),
            "cases_open": q("SELECT COUNT(*) FROM cases WHERE status='Open'"),
            "evidence": q("SELECT COUNT(*) FROM evidence"),
            "evidence_by_kind": kinds_evidence,
            "files_analyzed": q("SELECT COUNT(DISTINCT path) FROM analyses"),
            "hidden_data_detected": detected,
            "extraction_operations": q("SELECT COUNT(*) FROM extractions"),
            "extraction_success": q("SELECT COUNT(*) FROM extractions WHERE status='SUCCESS'"),
            "forensic_analyses": q("SELECT COUNT(*) FROM analyses"),
            "hash_verifications": q("SELECT COUNT(*) FROM hashes"),
            "findings": q("SELECT COUNT(*) FROM findings"),
            "findings_by_severity": sev,
            "reports": q("SELECT COUNT(*) FROM reports"),
            "tool_executions": q("SELECT COUNT(*) FROM tool_executions"),
            "metadata_snapshots": q("SELECT COUNT(*) FROM metadata_snapshots"),
            "log_entries": q("SELECT COUNT(*) FROM investigation_logs"),
            "analyses_by_kind": kinds,
            "extractions_by_technique": techniques,
        }


_DB: Database | None = None


def get_db() -> Database:
    global _DB
    if _DB is None:
        _DB = Database()
    return _DB


def reset_db_for_tests(path: Path) -> Database:
    global _DB
    _DB = Database(path)
    return _DB
