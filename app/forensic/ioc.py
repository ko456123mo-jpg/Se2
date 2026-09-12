"""Indicator-of-compromise extraction from strings/binary content (rule 47).

Regex-based IOC extraction is deliberately conservative: everything it reports
is an *indicator* that must be correlated with behaviour before it becomes a
finding.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.core.models import IocSet

IP_RE = re.compile(rb"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
                   rb"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b")
URL_RE = re.compile(rb"\b(?:https?|ftp)://[^\s\"'<>\\)]{4,300}", re.IGNORECASE)
DOMAIN_RE = re.compile(rb"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
                       rb"(?:com|net|org|info|ru|cn|io|xyz|top|onion|local|internal)\b",
                       re.IGNORECASE)
EMAIL_RE = re.compile(rb"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
WIN_PATH_RE = re.compile(rb"(?i)\b[A-Za-z]:\\(?:[^\s\\/:*?\"<>|]{1,80}\\){0,10}"
                         rb"[^\s\\/:*?\"<>|]{1,80}")
UNIX_PATH_RE = re.compile(rb"(?:/usr/|/etc/|/var/|/tmp/|/opt/|/home/|/root/)"
                          rb"[A-Za-z0-9._/-]{1,200}")
REG_RE = re.compile(rb"(?i)\bHKEY_[A-Z_]+\\[^\s\"']{3,200}")

SUSPICIOUS_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("powershell", re.compile(rb"(?i)powershell(\.exe)?\s+-(e|enc|w\s+hidden|nop)")),
    ("cmd-shell", re.compile(rb"(?i)cmd(\.exe)?\s+/c\s")),
    ("registry-run-key", re.compile(rb"(?i)\\CurrentVersion\\Run")),
    ("scheduled-task", re.compile(rb"(?i)schtasks(\.exe)?\s+/create")),
    ("service-install", re.compile(rb"(?i)sc(\.exe)?\s+create")),
    ("credential-store", re.compile(rb"(?i)(mimikatz|lsass|sekurlsa|wdigest)")),
    ("process-injection", re.compile(rb"(?i)(VirtualAllocEx|WriteProcessMemory|"
                                     rb"CreateRemoteThread|NtMapViewOfSection)")),
    ("anti-debug", re.compile(rb"(?i)(IsDebuggerPresent|CheckRemoteDebuggerPresent|"
                              rb"NtQueryInformationProcess)")),
    ("anti-vm", re.compile(rb"(?i)(vmware|vbox|qemu|virtualbox|vboxservice)")),
    ("downloader", re.compile(rb"(?i)(URLDownloadToFile|WinHttpOpen|InternetOpenUrl)")),
    ("ransom-note", re.compile(rb"(?i)(your files (have been )?encrypted|decrypt(ion)? "
                                rb"instructions|bitcoin|monero wallet)")),
    ("keylogger", re.compile(rb"(?i)(SetWindowsHookEx|GetAsyncKeyState)")),
    ("base64-blob", re.compile(rb"[A-Za-z0-9+/]{200,}={0,2}")),
    ("pyinstaller-marker", re.compile(rb"(pyi-|PYZ-00\.pyz|MEIPASS|python3\d\d?\.dll)")),
    ("stego-marker", re.compile(rb"(SNXB|SNX1|SNXEOF0001|SNXNET1)")),
]

PRIVATE_IP_PREFIXES = ("10.", "127.", "192.168.", "172.16.", "172.17.", "172.18.",
                       "172.19.", "172.2", "172.30.", "172.31.", "0.", "255.")


def _decode_all(matches: list[bytes], limit: int = 200) -> list[str]:
    seen: list[str] = []
    for raw in matches:
        text = raw.decode("utf-8", errors="ignore").strip()
        if text and text not in seen:
            seen.append(text)
        if len(seen) >= limit:
            break
    return seen


def extract(data: bytes, *, include_private_ips: bool = False,
            limit: int = 200) -> IocSet:
    """Extract IOCs from a byte buffer (typically the output of ``strings``)."""
    ips = _decode_all(IP_RE.findall(data), limit)
    if not include_private_ips:
        ips = [ip for ip in ips if not ip.startswith(PRIVATE_IP_PREFIXES)]
    urls = _decode_all(URL_RE.findall(data), limit)
    domains = _decode_all(DOMAIN_RE.findall(data), limit)
    emails = _decode_all(EMAIL_RE.findall(data), limit)
    paths = _decode_all(WIN_PATH_RE.findall(data) + UNIX_PATH_RE.findall(data), limit)
    registry = _decode_all(REG_RE.findall(data), limit)
    suspicious: list[str] = []
    for label, pattern in SUSPICIOUS_PATTERNS:
        found = pattern.findall(data)
        if found:
            sample = found[0]
            sample = sample.decode("utf-8", errors="ignore") if isinstance(sample, bytes) \
                else str(sample)
            suspicious.append(f"{label} (x{len(found)}): {sample[:80]}")
    return IocSet(ips=ips, domains=domains, urls=urls, emails=emails, paths=paths,
                  registry=registry, suspicious_strings=suspicious[:limit])


def extract_file(path: Path, max_bytes: int = 32 * 1024 * 1024) -> IocSet:
    p = Path(path)
    with open(p, "rb") as fh:
        return extract(fh.read(max_bytes))


def summarize(iocs: IocSet) -> str:
    parts = [f"{len(getattr(iocs, name))} {name}" for name in
             ("ips", "domains", "urls", "emails", "paths", "registry")]
    return ", ".join(parts) + f", {len(iocs.suspicious_strings)} suspicious patterns"
