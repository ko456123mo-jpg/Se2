"""Structured logging (project rule 85).

Two sinks:

* ``logs/stegonexus.log``  - JSON lines, machine readable, exportable.
* ``logs/stegonexus-YYYY-MM-DD.log`` - human readable rolling daily file.

Every record carries: timestamp, level, module, action, case_id, evidence_id,
tool, status, message.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import get_config

_JSON_FIELDS = ("timestamp", "level", "module", "action", "case_id",
                "evidence_id", "tool", "status", "message")
_configured = False
_LOGGERS: dict[str, logging.Logger] = {}


class StructuredFormatter(logging.Formatter):
    """Emit JSON lines for the machine-readable sink."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        payload = {name: getattr(record, name, None) for name in _JSON_FIELDS}
        payload["timestamp"] = datetime.fromtimestamp(
            record.created).strftime("%Y-%m-%dT%H:%M:%S.%f")
        payload["level"] = record.levelname
        payload["module"] = getattr(record, "module_name", record.module)
        payload["message"] = record.getMessage()
        payload = {k: v for k, v in payload.items() if v not in (None, "")}
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class HumanFormatter(logging.Formatter):
    """Emit readable lines for the daily log file."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        stamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        module = getattr(record, "module_name", record.module)
        action = getattr(record, "action", "-")
        return (f"{stamp} [{record.levelname:<8}] {module:<16} "
                f"{action:<22} {record.getMessage()}")


def setup_logging(verbose: bool | None = None) -> None:
    """Configure root handlers once per process."""
    global _configured
    cfg = get_config()
    if verbose is None:
        verbose = cfg.verbose_logs
    root = logging.getLogger("stegonexus")
    root.setLevel(logging.DEBUG)
    if _configured:
        return
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)

    json_handler = logging.FileHandler(cfg.logs_dir / "stegonexus.log", encoding="utf-8")
    json_handler.setFormatter(StructuredFormatter())

    daily = logging.handlers.TimedRotatingFileHandler(
        cfg.logs_dir / "stegonexus-daily.log", when="midnight",
        backupCount=14, encoding="utf-8")
    daily.setFormatter(HumanFormatter())

    console = logging.StreamHandler()
    console.setFormatter(HumanFormatter())
    console.setLevel(logging.DEBUG if verbose else logging.WARNING)

    for handler in (json_handler, daily, console):
        root.addHandler(handler)
    root.propagate = False
    _configured = True


def get_logger(module_name: str) -> logging.Logger:
    setup_logging()
    logger = _LOGGERS.get(module_name)
    if logger is None:
        logger = logging.getLogger(f"stegonexus.{module_name}")
        _LOGGERS[module_name] = logger
    return logger


def log_event(module: str, action: str, message: str, *, level: int = logging.INFO,
              case_id: int | None = None, evidence_id: int | None = None,
              tool: str | None = None, status: str = "OK", **extra: Any) -> None:
    """Emit one structured event."""
    logger = get_logger(module)
    logger.log(level, message, extra={
        "module_name": module, "action": action, "case_id": case_id,
        "evidence_id": evidence_id, "tool": tool, "status": status, **extra})


def export_log(destination: Path, last_n: int = 5000) -> Path:
    """Copy the JSON log into an export file (used by the Logs screen)."""
    cfg = get_config()
    source = cfg.logs_dir / "stegonexus.log"
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        destination.write_text("", encoding="utf-8")
        return destination
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    destination.write_text("\n".join(lines[-last_n:]) + "\n", encoding="utf-8")
    return destination
