"""Settings service (centralised configuration, project rule 64)."""
from __future__ import annotations

from app.core.config import AppConfig, ToolOverrides, get_config
from app.core.logger import log_event, setup_logging
from app.storage.database import get_db


def current() -> dict:
    cfg = get_config()
    return {
        "root": str(cfg.root), "data_dir": str(cfg.data_dir),
        "cases_dir": str(cfg.cases_dir), "reports_dir": str(cfg.reports_dir),
        "logs_dir": str(cfg.logs_dir), "samples_dir": str(cfg.samples_dir),
        "database": str(cfg.db_path), "config_file": str(cfg.config_path),
        "theme": cfg.theme, "tool_timeout": cfg.tool_timeout,
        "investigator": cfg.investigator,
        "auto_hash_on_import": cfg.auto_hash_on_import,
        "read_only_analysis": cfg.read_only_analysis,
        "network_authorized_lab": cfg.network_authorized_lab,
        "verbose_logs": cfg.verbose_logs,
        "tool_overrides": cfg.tool_overrides.as_dict(),
    }


def save(**changes) -> dict:
    """Persist supported settings and reload the affected subsystems."""
    cfg = get_config()
    allowed = {"theme", "tool_timeout", "investigator", "auto_hash_on_import",
               "read_only_analysis", "network_authorized_lab", "verbose_logs"}
    applied: dict = {}
    for key, value in changes.items():
        if key == "tool_overrides" and isinstance(value, dict):
            for tool, path in value.items():
                if hasattr(cfg.tool_overrides, tool):
                    setattr(cfg.tool_overrides, tool, str(path or ""))
            applied["tool_overrides"] = value
            continue
        if key in allowed:
            setattr(cfg, key, value)
            applied[key] = value
    cfg.save()
    if "verbose_logs" in applied:
        setup_logging(verbose=bool(applied["verbose_logs"]))
    get_db().log_action(action="Settings Updated", module="settings",
                        target=", ".join(sorted(applied)),
                        result=str(applied)[:400])
    log_event("settings", "update", f"changed {sorted(applied)}")
    return current()


def reset_theme(theme: str = "dark") -> dict:
    if theme not in ("dark", "light"):
        from app.core.exceptions import ValidationError

        raise ValidationError("Theme must be 'dark' or 'light'.")
    return save(theme=theme)
