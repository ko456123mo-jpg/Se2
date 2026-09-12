"""Domain dataclasses shared by services, storage and GUI.

These are plain data holders - no Qt imports - so the engine layer stays
testable headlessly.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.constants import HASH_ALGORITHMS


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class HashResult:
    path: str
    size: int
    hashes: dict[str, str] = field(default_factory=dict)
    elapsed_ms: float = 0.0
    created: str = field(default_factory=now_iso)

    @property
    def sha256(self) -> str:
        return self.hashes.get("sha256", "")

    def to_row(self) -> dict:
        row = asdict(self)
        row["hashes"] = json_dumps_dict(self.hashes)
        return row


def json_dumps_dict(data: dict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, sort_keys=True)


@dataclass
class ToolResult:
    tool: str
    argv: list[str]
    available: bool
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    elapsed_ms: float = 0.0
    error: str = ""
    timed_out: bool = False
    truncated: bool = False
    parsed: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.available and not self.timed_out and self.returncode == 0

    @property
    def status(self) -> str:
        if self.timed_out:
            return "TIMEOUT"
        if not self.available:
            return "UNAVAILABLE"
        return "OK" if self.ok else "ERROR"

    def command_display(self) -> str:
        from app.core.security import shell_quote_list

        return shell_quote_list(self.argv)

    def summary(self) -> str:
        return (f"{self.tool}: {self.status} rc={self.returncode} "
                f"{self.elapsed_ms:.0f}ms out={len(self.stdout)}B err={len(self.stderr)}B")


@dataclass
class MetadataEntry:
    group: str
    tag: str
    value: str

    def as_row(self) -> list[str]:
        return [self.group, self.tag, self.value]


@dataclass
class MetadataSnapshot:
    path: str
    source: str                 # "exiftool" | "pillow-fallback" | "ffprobe"
    available: bool
    entries: list[MetadataEntry] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)
    error: str = ""
    created: str = field(default_factory=now_iso)

    @property
    def count(self) -> int:
        return len(self.entries)


@dataclass
class StegoOperation:
    """One hide/extract operation result."""

    technique: str
    operation: str              # "hide" | "extract" | "analyse"
    status: str                 # "SUCCESS" | "FAILED" | "PARTIAL"
    input_path: str = ""
    output_path: str = ""
    payload_bytes: int = 0
    capacity_bytes: int = 0
    key_fingerprint: str = ""
    input_hash: str = ""
    output_hash: str = ""
    extracted_matches: bool | None = None
    engine: str = ""            # native | steghide | ffmpeg | scapy ...
    status_label: str = ""      # constants.Status.*
    messages: list[str] = field(default_factory=list)
    error: str = ""
    elapsed_ms: float = 0.0
    case_id: int | None = None
    evidence_id: int | None = None
    details: dict[str, Any] = field(default_factory=dict)
    created: str = field(default_factory=now_iso)

    @property
    def ok(self) -> bool:
        return self.status == "SUCCESS"


@dataclass
class Finding:
    case_id: int
    category: str
    severity: str
    title: str
    description: str
    indicator: str = ""
    evidence_ref: str = ""
    confidence: str = "Medium"
    investigator: str = ""
    finding_id: int | None = None
    created: str = field(default_factory=now_iso)


@dataclass
class Case:
    title: str
    description: str = ""
    investigator: str = ""
    status: str = "Open"
    case_id: int | None = None
    number: str = ""
    created: str = field(default_factory=now_iso)
    closed: str | None = None
    notes: str = ""
    tags: str = ""


@dataclass
class Evidence:
    case_id: int
    name: str
    path: str
    kind: str = "original"
    source: str = ""
    notes: str = ""
    size: int = 0
    mime: str = ""
    md5: str = ""
    sha1: str = ""
    sha256: str = ""
    sha512: str = ""
    status: str = "imported"
    evidence_id: int | None = None
    created: str = field(default_factory=now_iso)

    def hashes_dict(self) -> dict[str, str]:
        return {a: getattr(self, a, "") for a in HASH_ALGORITHMS}


@dataclass
class EntropyReport:
    path: str
    size: int
    entropy: float
    interpretation: str
    blocks: list[dict[str, Any]] = field(default_factory=list)
    block_size: int = 0
    min_block: float = 0.0
    max_block: float = 0.0
    high_entropy_ratio: float = 0.0


@dataclass
class NetworkPacketInfo:
    index: int
    timestamp: str
    src: str
    dst: str
    proto: str
    length: int
    sport: int | None = None
    dport: int | None = None
    ip_id: int | None = None
    ttl: int | None = None
    payload_len: int = 0
    payload_preview: str = ""
    notes: str = ""


@dataclass
class PacketAnalysis:
    """Forensic interpretation layer output (project rule 40)."""

    observation: str
    indicator: str
    context: list[str]
    correlation: list[str]
    assessment: str
    confidence: str = "Low"
    packets_examined: int = 0
    anomalous: list[int] = field(default_factory=list)


@dataclass
class IocSet:
    ips: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    registry: list[str] = field(default_factory=list)
    suspicious_strings: list[str] = field(default_factory=list)

    def total(self) -> int:
        return sum(len(getattr(self, f)) for f in
                   ("ips", "domains", "urls", "emails", "paths", "registry"))

    def as_dict(self) -> dict[str, list[str]]:
        return asdict(self)


def path_str(p: str | Path) -> str:
    return str(Path(p).expanduser())
