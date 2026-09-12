"""Centralised configuration (project rule 64 - no hard-coded user paths).

Resolution order:
  1. ``STEGONEXUS_HOME`` environment variable
  2. ``~/.local/share/StegoNexus`` (XDG data dir)

The project tree shipped with the application (cases/, reports/, logs/, samples/)
is used when it is writable, otherwise the XDG location is used.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]  # project root (StegoNexus/)
CONFIG_FILE_NAME = "stegonexus.json"

DEFAULT_THEME = "dark"


@dataclass
class ToolOverrides:
    """Optional manual paths for external tools (Settings screen)."""

    exiftool: str = ""
    steghide: str = ""
    binwalk: str = ""
    foremost: str = ""
    zsteg: str = ""
    ffmpeg: str = ""
    ffprobe: str = ""
    tshark: str = ""
    wireshark: str = ""
    audacity: str = ""
    cyberhide: str = ""
    deepsound: str = ""
    coagula: str = ""

    def as_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class AppConfig:
    root: Path
    theme: str = DEFAULT_THEME
    tool_timeout: int = 120
    max_evidence_bytes: int = 4 * 1024 * 1024 * 1024
    investigator: str = "Investigator"
    auto_hash_on_import: bool = True
    read_only_analysis: bool = True
    network_authorized_lab: bool = False
    verbose_logs: bool = False
    tool_overrides: ToolOverrides = field(default_factory=ToolOverrides)

    # ------------------------------------------------------------- directories
    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def cases_dir(self) -> Path:
        return self.root / "cases"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def samples_dir(self) -> Path:
        return self.root / "samples"

    @property
    def resources_dir(self) -> Path:
        return self.root / "resources"

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "stegonexus.db"

    @property
    def config_path(self) -> Path:
        return self.data_dir / CONFIG_FILE_NAME

    # ------------------------------------------------------------------- setup
    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.cases_dir, self.reports_dir, self.logs_dir,
                  self.samples_dir, self.temp_dir):
            d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.data_dir, 0o700)
        except OSError:
            pass

    # ----------------------------------------------------------- serialisation
    def to_dict(self) -> dict:
        d = asdict(self)
        d["root"] = str(self.root)
        d["tool_overrides"] = self.tool_overrides.as_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        root = Path(data.get("root", str(APP_DIR))).expanduser()
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in data.items() if k in known and k != "root"}
        overrides = kwargs.pop("tool_overrides", {}) or {}
        cfg = cls(root=root, **kwargs)
        cfg.tool_overrides = ToolOverrides(**{
            k: v for k, v in overrides.items()
            if k in ToolOverrides.__dataclass_fields__})  # type: ignore[attr-defined]
        return cfg

    def save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def resolve_root() -> Path:
    """Pick the workspace root (env var > writable project tree > XDG data dir)."""
    env = os.environ.get("STEGONEXUS_HOME")
    if env:
        return Path(env).expanduser().resolve()
    if APP_DIR.is_dir() and os.access(APP_DIR, os.W_OK):
        return APP_DIR
    xdg = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return (xdg / "StegoNexus").resolve()


_CONFIG: AppConfig | None = None


def get_config(reload: bool = False) -> AppConfig:
    """Return the process-wide configuration, creating directories on first use."""
    global _CONFIG
    if _CONFIG is not None and not reload:
        return _CONFIG
    root = resolve_root()
    cfg: AppConfig
    cfg_path = root / "data" / CONFIG_FILE_NAME
    if cfg_path.exists():
        try:
            cfg = AppConfig.from_dict(json.loads(cfg_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError):
            cfg = AppConfig(root=root)
    else:
        cfg = AppConfig(root=root)
    cfg.ensure_dirs()
    _CONFIG = cfg
    return cfg


def reset_config_for_tests(root: Path) -> AppConfig:
    """Point the process-wide config at a throwaway root (used by the test-suite)."""
    global _CONFIG
    _CONFIG = AppConfig(root=Path(root))
    _CONFIG.ensure_dirs()
    return _CONFIG
