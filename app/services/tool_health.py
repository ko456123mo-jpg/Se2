"""Tool Health / Dependency Center (project rule 60).

Probes every external dependency and Python library the framework can use and
reports the *measured* state.  Nothing here is ever assumed: a tool that is not
found on PATH is reported as unavailable, with the exact Kali package that
provides it.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass, field
from typing import Any

from app.services.tool_executor import executor

#: (name, kind, modules, required, version-args, kali-install-hint)
TOOL_REGISTRY: list[dict[str, Any]] = [
    {"name": "exiftool", "kind": "binary", "modules": ["Metadata", "Forensics", "Audio"],
     "required": True, "version_args": ["-ver"],
     "install": "sudo apt install libimage-exiftool-perl"},
    {"name": "file", "kind": "binary", "modules": ["Forensics", "Malware"],
     "required": True, "version_args": ["--version"], "install": "preinstalled on Kali"},
    {"name": "strings", "kind": "binary", "modules": ["Forensics", "Malware"],
     "required": True, "version_args": ["--version"],
     "install": "sudo apt install binutils"},
    {"name": "binwalk", "kind": "binary", "modules": ["Forensics"],
     "required": True, "version_args": ["-h"], "install": "sudo apt install binwalk"},
    {"name": "steghide", "kind": "binary", "modules": ["Image", "Audio"],
     "required": True, "version_args": ["--version"], "install": "sudo apt install steghide"},
    {"name": "foremost", "kind": "binary", "modules": ["Forensics"],
     "required": True, "version_args": ["-V"], "install": "sudo apt install foremost"},
    {"name": "zsteg", "kind": "binary", "modules": ["Forensics", "Image"],
     "required": False, "version_args": ["--version"],
     "install": "sudo gem install zsteg   (Ruby - no Debian package)"},
    {"name": "ffmpeg", "kind": "binary", "modules": ["Video", "Audio"],
     "required": True, "version_args": ["-version"], "install": "sudo apt install ffmpeg"},
    {"name": "ffprobe", "kind": "binary", "modules": ["Video", "Audio"],
     "required": True, "version_args": ["-version"], "install": "sudo apt install ffmpeg"},
    {"name": "tshark", "kind": "binary", "modules": ["Network"],
     "required": False, "version_args": ["--version"], "install": "sudo apt install tshark"},
    {"name": "wireshark", "kind": "binary", "modules": ["Network"],
     "required": False, "version_args": ["--version"], "install": "sudo apt install wireshark"},
    {"name": "audacity", "kind": "binary", "modules": ["Audio"],
     "required": False, "version_args": ["--version"], "install": "sudo apt install audacity"},
    {"name": "rar", "kind": "binary", "modules": ["Malware"],
     "required": False, "version_args": ["--version"], "install": "sudo apt install rar"},
    {"name": "unrar", "kind": "binary", "modules": ["Malware"],
     "required": False, "version_args": ["--version"], "install": "sudo apt install unrar"},
    {"name": "pyinstaller", "kind": "binary", "modules": ["Malware"],
     "required": False, "version_args": ["--version"], "install": "pip install pyinstaller"},
    # ------------------------------------------------------------- python libs
    {"name": "PySide6", "kind": "python", "modules": ["GUI"], "required": True,
     "install": "pip install PySide6"},
    {"name": "PIL", "kind": "python", "modules": ["Image"], "required": True,
     "install": "pip install Pillow"},
    {"name": "numpy", "kind": "python", "modules": ["Audio", "Video"], "required": True,
     "install": "pip install numpy"},
    {"name": "cryptography", "kind": "python", "modules": ["Malware", "Container hiding"],
     "required": True, "install": "pip install cryptography"},
    {"name": "scapy", "kind": "python", "modules": ["Network"], "required": False,
     "install": "pip install scapy"},
    # -------------------------------------------------- Windows-only references
    {"name": "cyberhide", "kind": "binary", "modules": ["Image"], "required": False,
     "version_args": ["--help"], "install": "Windows GUI tool - external integration"},
    {"name": "deepsound", "kind": "binary", "modules": ["Audio"], "required": False,
     "version_args": ["--help"], "install": "Windows GUI tool - external integration"},
    {"name": "coagula", "kind": "binary", "modules": ["Audio"], "required": False,
     "version_args": ["--help"], "install": "Windows GUI tool - external integration"},
    {"name": "openpuff", "kind": "binary", "modules": ["Video"], "required": False,
     "version_args": ["--help"], "install": "Windows GUI tool - external integration"},
]

REFERENCE_TOOLS = {"cyberhide", "deepsound", "coagula", "openpuff"}


@dataclass
class ToolStatus:
    name: str
    kind: str
    modules: list[str] = field(default_factory=list)
    required: bool = False
    available: bool = False
    path: str = ""
    version: str = ""
    install: str = ""
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name, "kind": self.kind, "modules": self.modules,
            "required": self.required, "available": self.available,
            "path": self.path, "version": self.version, "install": self.install,
            "note": self.note, "classification": self.classification,
        }

    @property
    def classification(self) -> str:
        if self.available:
            return "INTEGRATED"
        if self.name in REFERENCE_TOOLS:
            return "REFERENCE"
        return "UNAVAILABLE"


class ToolHealth:
    """Availability probe used by the Tool Health screen and every module."""

    def __init__(self):
        self._cache: dict[str, ToolStatus] = {}

    def check(self, name: str, *, refresh: bool = False) -> ToolStatus:
        if name in self._cache and not refresh:
            return self._cache[name]
        entry = next((e for e in TOOL_REGISTRY if e["name"] == name), None)
        if entry is None:
            entry = {"name": name, "kind": "binary", "modules": [], "required": False,
                     "version_args": ["--version"], "install": ""}
        status = ToolStatus(name=name, kind=entry["kind"], modules=entry["modules"],
                            required=entry["required"], install=entry["install"])
        if entry["kind"] == "python":
            spec = importlib.util.find_spec(name) if _safe_find(name) else None
            status.available = spec is not None
            if status.available:
                status.path = str(getattr(spec, "origin", "") or "")
                status.version = _module_version(name)
        else:
            path = executor.resolve(name)
            status.available = path is not None
            status.path = path or ""
            if path:
                status.version = executor.version(name, entry.get("version_args", ["--version"]))
        if name in REFERENCE_TOOLS:
            status.note = ("External practical/reference tool from the course material. "
                           "StegoNexus detects it and documents the workflow; it does not "
                           "pretend to embed it.")
        self._cache[name] = status
        return status

    def check_all(self, refresh: bool = True) -> list[ToolStatus]:
        return [self.check(e["name"], refresh=refresh) for e in TOOL_REGISTRY]

    def available_names(self) -> set[str]:
        return {s.name for s in self.check_all() if s.available}

    def missing_required(self) -> list[str]:
        return [s.name for s in self.check_all() if s.required and not s.available]

    def summary(self) -> dict[str, Any]:
        statuses = self.check_all()
        return {
            "total": len(statuses),
            "available": sum(1 for s in statuses if s.available),
            "missing_required": self.missing_required(),
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "rows": [s.as_dict() for s in statuses],
        }


def _safe_find(name: str) -> bool:
    try:
        return True
    finally:
        pass


def _module_version(name: str) -> str:
    try:
        import importlib

        mod = importlib.import_module(name)
        for attr in ("__version__", "VERSION", "version"):
            value = getattr(mod, attr, None)
            if isinstance(value, str):
                return value
            if isinstance(value, tuple):
                return ".".join(str(v) for v in value)
        return "installed"
    except Exception:  # pragma: no cover - probing must never raise
        return "installed"


def has(name: str) -> bool:
    """Convenience used by feature gates across the app."""
    if name in ("scapy", "PIL", "numpy", "cryptography", "PySide6"):
        return importlib.util.find_spec(name) is not None
    return shutil.which(name) is not None


health = ToolHealth()
