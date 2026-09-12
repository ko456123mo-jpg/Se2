"""Input validation, path safety and general hardening (project rules 66/69).

Nothing in this module executes anything; it only decides whether an operation
may proceed.
"""
from __future__ import annotations

import hashlib
import os
import re
import shlex
import unicodedata
from pathlib import Path

from app.core.constants import MAX_EVIDENCE_BYTES, MAX_INJECT_METADATA_VALUE
from app.core.exceptions import PathError, ValidationError

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._ -]{1,120}$")
_TRAVERSAL_PARTS = {"..", "~"}


def validate_non_empty(value: str | None, field: str) -> str:
    if value is None or not str(value).strip():
        raise ValidationError(f"{field} must not be empty.")
    return str(value).strip()


def validate_range(value: int, low: int, high: int, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer.")
    if value < low or value > high:
        raise ValidationError(f"{field} must be between {low} and {high}.")
    return value


def safe_filename(name: str, field: str = "filename") -> str:
    """Return a sanitised file name (no path separators, no traversal)."""
    name = unicodedata.normalize("NFKC", str(name)).strip()
    name = name.replace("\x00", "")
    if not _SAFE_NAME.match(name):
        raise ValidationError(
            f"{field} contains unsafe characters "
            "(allowed: letters, digits, space, '.', '_', '-', max 120 chars).")
    if name in {".", ".."}:
        raise ValidationError(f"{field} must be a real file name.")
    return name


def safe_path(path: str | os.PathLike, must_exist: bool = True,
              must_be_file: bool = False, must_be_dir: bool = False) -> Path:
    """Resolve a user supplied path and reject traversal / special files."""
    p = Path(str(path)).expanduser()
    parts = set(p.parts)
    if parts & _TRAVERSAL_PARTS and not p.is_absolute():
        raise PathError("Path traversal ('..' / '~') is not allowed.")
    try:
        resolved = p.resolve()
    except OSError as exc:  # pragma: no cover - platform specific
        raise PathError(f"Cannot resolve path: {exc}") from exc
    if must_exist and not resolved.exists():
        raise PathError(
            f"Path does not exist: {resolved}. Use the Browse button to pick an "
            f"existing file, or create it first.")
    if must_be_file and not resolved.is_file():
        raise PathError(f"Not a regular file: {resolved}")
    if must_be_dir and not resolved.is_dir():
        raise PathError(f"Not a directory: {resolved}")
    if resolved.exists() and (resolved.is_fifo() or resolved.is_socket()
                              or resolved.is_block_device() or resolved.is_char_device()):
        raise PathError("Special files (fifo/socket/device) are rejected.")
    return resolved


def validate_output_path(path: str | os.PathLike, overwrite: bool = False) -> Path:
    """Validate a destination path; refuse to clobber existing files silently."""
    p = Path(str(path)).expanduser()
    parent = p.parent
    if not parent.exists():
        raise PathError(f"Parent directory does not exist: {parent}")
    if not parent.is_dir():
        raise PathError(f"Parent path is not a directory: {parent}")
    if not os.access(parent, os.W_OK):
        raise PathError(f"Parent directory is not writable: {parent}")
    if p.exists():
        if not overwrite:
            raise PathError(f"Output file already exists: {p}")
        if not p.is_file():
            raise PathError(f"Output path exists and is not a file: {p}")
        if not os.access(p, os.W_OK):
            raise PathError(
                f"Output file exists but is not writable (it may be owned by another "
                f"user, e.g. created while running with sudo): {p}. Remove it or "
                f"choose a different output name.")
    return p


def validate_readable_file(path: str | os.PathLike,
                           max_bytes: int = MAX_EVIDENCE_BYTES) -> Path:
    p = safe_path(path, must_exist=True, must_be_file=True)
    size = p.stat().st_size
    if size == 0:
        raise ValidationError(f"File is empty: {p}")
    if size > max_bytes:
        raise ValidationError(
            f"File is larger than the configured limit "
            f"({size} > {max_bytes} bytes).")
    return p


def validate_metadata_value(value: str, field: str) -> str:
    value = validate_non_empty(value, field)
    if len(value) > MAX_INJECT_METADATA_VALUE:
        raise ValidationError(f"{field} exceeds {MAX_INJECT_METADATA_VALUE} characters.")
    if any(ord(c) < 0x20 and c not in "\t\n" for c in value):
        raise ValidationError(f"{field} contains control characters.")
    return value


def validate_key(key: str, field: str = "key") -> str:
    key = validate_non_empty(key, field)
    if len(key) < 4:
        raise ValidationError(f"{field} must be at least 4 characters.")
    if len(key) > 256:
        raise ValidationError(f"{field} must be at most 256 characters.")
    return key


def validate_port(port: int, field: str = "port") -> int:
    return validate_range(port, 1, 65535, field)


def validate_ip(addr: str, field: str = "address") -> str:
    import ipaddress

    addr = validate_non_empty(addr, field)
    try:
        ipaddress.ip_address(addr)
    except ValueError as exc:
        raise ValidationError(f"{field} is not a valid IP address: {addr}") from exc
    return addr


def is_loopback_or_private(addr: str) -> bool:
    """True only for loopback / RFC1918 / link-local addresses (lab safety gate)."""
    import ipaddress

    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return bool(ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_unspecified)


def shell_quote_list(args: list[str]) -> str:
    """Render an argv list for display only - never for execution."""
    return " ".join(shlex.quote(a) for a in args)


def short_hash(path: Path, algorithm: str = "sha256", limit: int = 1024 * 1024) -> str:
    """Quick partial hash used for de-duplication checks (not forensic evidence)."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        h.update(fh.read(limit))
    h.update(str(path.stat().st_size).encode())
    return h.hexdigest()


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024.0:
            return f"{num:,.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024.0
    return f"{num:,.1f} PB"


def looks_like_flag(value: str) -> bool:
    """Detect argument-injection attempts (values that start with '-')."""
    return str(value).startswith("-")
