"""Forensics & analysis service (project rule 13).

Tools wired through the ToolExecutor: ``file``, ``strings``, ``exiftool``,
``binwalk``, ``steghide info``, ``foremost``, ``zsteg``, plus the native
Shannon-entropy engine.  Every result records whether the tool was actually
available - an unavailable tool is reported as such and never simulated.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from app.core.constants import AnalysisType, Status
from app.core.exceptions import ToolUnavailable, ValidationError
from app.core.logger import log_event
from app.core.security import safe_path, validate_readable_file
from app.forensic.entropy import entropy_file
from app.services.tool_executor import executor
from app.storage.database import get_db

STRINGS_INTEREST = re.compile(
    r"(?i)(https?://|ftp://|\\\\|/etc/|C:\\|cmd\.exe|powershell|passwd|password|"
    r"secret|token|api[_-]?key|BEGIN [A-Z ]*PRIVATE KEY|SELECT .* FROM|"
    r"INSERT INTO|eval\(|base64|mimikatz|schtasks|regsvr32|rundll32|SNX[A-Z0-9]+)")


def _record(kind: str, path: str, tool: str, status: str, summary: str,
            payload: dict, elapsed: float, case_id: int | None,
            evidence_id: int | None) -> dict:
    db = get_db()
    db.add_analysis({"case_id": case_id, "evidence_id": evidence_id, "kind": kind,
                     "path": path, "tool": tool, "status": status,
                     "summary": summary[:1000], "payload": payload,
                     "elapsed_ms": elapsed})
    db.log_action(action="Forensic Tool Executed", module="forensics", target=path,
                  case_id=case_id, evidence_id=evidence_id, tool=tool,
                  result=summary[:400], status=status)
    log_event("forensics", kind, f"{tool} on {Path(path).name}: {status}",
              case_id=case_id, tool=tool, status=status)
    return {"kind": kind, "tool": tool, "status": status, "summary": summary,
            **payload}


# ------------------------------------------------------------------------- file
def file_type(path: Path, case_id: int | None = None,
              evidence_id: int | None = None) -> dict:
    target = validate_readable_file(path)
    if not executor.is_available("file"):
        raise ToolUnavailable("The 'file' utility is not installed.")
    result = executor.run("file", ["--brief", "--mime-type", str(target)],
                          case_id=case_id)
    mime = result.stdout.strip() if result.ok else ""
    result2 = executor.run("file", ["--brief", str(target)], case_id=case_id)
    description = result2.stdout.strip() if result2.ok else ""
    suffix = target.suffix.lower().lstrip(".")
    mismatch = ""
    if suffix and mime:
        expected = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "pdf": "application/pdf", "zip": "application/zip",
                    "txt": "text/plain", "mp3": "audio/mpeg", "wav": "audio/x-wav",
                    "mp4": "video/mp4", "gz": "application/gzip"}.get(suffix)
        if expected and expected not in mime and mime != "application/octet-stream":
            mismatch = (f"Extension '.{suffix}' usually maps to {expected} but the "
                        f"content is {mime}.")
    return _record(AnalysisType.FILE_TYPE, str(target), "file", result.status,
                   f"{mime or 'unknown'} - {description[:120]}",
                   {"mime": mime, "description": description, "mismatch": mismatch,
                    "command": result.command_display(),
                    "returncode": result.returncode,
                    "stderr": result.stderr.strip()[:300]},
                   result.elapsed_ms, case_id, evidence_id)


# ---------------------------------------------------------------------- strings
def strings(path: Path, min_length: int = 6, encoding: str = "auto",
            case_id: int | None = None, evidence_id: int | None = None) -> dict:
    target = validate_readable_file(path)
    if not 1 <= min_length <= 64:
        raise ValidationError("min_length must be between 1 and 64.")
    if encoding not in ("auto", "single", "big", "little", "utf8"):
        raise ValidationError("encoding must be one of auto/single/big/little/utf8.")
    if not executor.is_available("strings"):
        raise ToolUnavailable("binutils 'strings' is not installed.")
    args = ["-n", str(min_length)]
    if encoding == "single":
        args.append("-e s")
    elif encoding == "big":
        args.append("-e b")
    elif encoding == "little":
        args.append("-e l")
    elif encoding == "utf8":
        args.append("-e S")
    args.append(str(target))
    result = executor.run("strings", args, case_id=case_id)
    if not result.ok and not result.stdout:
        raise ToolUnavailable(f"strings failed: {result.stderr.strip()[:200]}")
    lines = result.stdout.splitlines()
    interesting = [ln for ln in lines if STRINGS_INTEREST.search(ln)]
    urls = sorted({m.group(0) for ln in lines
                   for m in re.finditer(r"(?i)https?://[^\s\"'<>]+", ln)})[:100]
    return _record(AnalysisType.STRINGS, str(target), "strings", result.status,
                   f"{len(lines)} strings, {len(interesting)} interesting, "
                   f"{len(urls)} URLs",
                   {"total": len(lines), "interesting": interesting[:200],
                    "urls": urls, "min_length": min_length, "encoding": encoding,
                    "sample": lines[:200], "truncated": result.truncated,
                    "command": result.command_display()},
                   result.elapsed_ms, case_id, evidence_id)


# ---------------------------------------------------------------------- entropy
def entropy(path: Path, block_size: int = 4096, case_id: int | None = None,
            evidence_id: int | None = None) -> dict:
    target = validate_readable_file(path)
    import time

    started = time.perf_counter()
    report = entropy_file(target, block_size=block_size)
    elapsed = (time.perf_counter() - started) * 1000
    return _record(AnalysisType.ENTROPY, str(target), "native-shannon", "OK",
                   f"H={report.entropy} bits/byte ({report.interpretation[:60]}...)",
                   {"entropy": report.entropy, "size": report.size,
                    "interpretation": report.interpretation,
                    "block_size": report.block_size, "min_block": report.min_block,
                    "max_block": report.max_block,
                    "high_entropy_ratio": report.high_entropy_ratio,
                    "blocks": report.blocks[:500], "formula":
                        "H(X) = -SUM p(x) log2 p(x)"},
                   elapsed, case_id, evidence_id)


# ---------------------------------------------------------------------- binwalk
def binwalk(path: Path, signature: bool = True, entropy_scan: bool = False,
            case_id: int | None = None, evidence_id: int | None = None) -> dict:
    target = validate_readable_file(path)
    if not executor.is_available("binwalk"):
        return _record(AnalysisType.BINWALK, str(target), "binwalk", Status.UNAVAILABLE,
                       "binwalk is not installed (sudo apt install binwalk)",
                       {"available": False,
                        "note": "Result not fabricated - install binwalk to run this."},
                       0.0, case_id, evidence_id)
    args = ["--quiet"]
    if signature:
        args.append("--signature")
    if entropy_scan:
        args.append("--entropy")
    args.append(str(target))
    result = executor.run("binwalk", args, case_id=case_id, timeout=300)
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    rows = []
    for line in lines:
        match = re.match(r"^(\d+)\s+(0x[0-9A-Fa-f]+)\s+(.*)$", line.strip())
        if match:
            rows.append({"offset": int(match.group(1)), "hex": match.group(2),
                         "description": match.group(3)})
    return _record(AnalysisType.BINWALK, str(target), "binwalk", result.status,
                   f"{len(rows)} embedded signature(s) detected",
                   {"available": True, "rows": rows[:500], "raw": lines[:200],
                    "command": result.command_display(),
                    "stderr": result.stderr.strip()[:300],
                    "caveat": "A signature match is an indicator, not proof of hidden "
                              "or malicious content."},
                   result.elapsed_ms, case_id, evidence_id)


# ------------------------------------------------------------------ steghide info
def steghide_info(path: Path, passphrase: str = "", case_id: int | None = None,
                  evidence_id: int | None = None) -> dict:
    """Run ``steghide info`` and interpret the real tool output.

    Steghide's ``info`` sub-command asks interactively whether it should look for
    embedded data, which fails without a terminal.  Supplying ``-p`` makes it
    non-interactive: with the correct passphrase it prints the embedded file
    details, and with a wrong one it reports that it could not extract data -
    which is itself a meaningful observation (the carrier is a supported format
    and may hold protected data).
    """
    target = validate_readable_file(path)
    if not executor.is_available("steghide"):
        return _record(AnalysisType.STEGHIDE_INFO, str(target), "steghide",
                       Status.UNAVAILABLE,
                       "steghide is not installed (sudo apt install steghide)",
                       {"available": False}, 0.0, case_id, evidence_id)
    result = executor.run("steghide", ["info", str(target), "-p", passphrase],
                          case_id=case_id)
    text = f"{result.stdout}\n{result.stderr}"
    parsed: dict = {"available": True, "raw": text.strip()[:2000],
                    "command": result.command_display(),
                    "returncode": result.returncode}
    for key, pattern in (("format", r"format:\s*(.+)"),
                         ("capacity", r"capacity:\s*(.+)"),
                         ("embedded_name", r'embedded file "([^"]+)"'),
                         ("embedded_size", r"size:\s*(.+)"),
                         ("encrypted", r"encrypted:\s*(.+)"),
                         ("compressed", r"compressed:\s*(.+)")):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            parsed[key] = match.group(1).strip()

    if "is not supported" in text:
        parsed["contains_data"] = None
        parsed["assessment"] = (
            "Carrier format is not supported by Steghide "
            f"({parsed.get('format', target.suffix or 'unknown')}). Steghide works "
            "with JPEG, BMP, WAV and AU. Use the native LSB engine, binwalk or the "
            "entropy analyser for this file.")
        status = "UNSUPPORTED_FORMAT"
    elif "embedded file" in parsed or parsed.get("embedded_name"):
        parsed["contains_data"] = True
        parsed["assessment"] = (
            f"Steghide reports embedded data: '{parsed.get('embedded_name', '?')}' "
            f"({parsed.get('embedded_size', '?')}, "
            f"{parsed.get('encrypted', 'encryption unknown')}). Extract it with the "
            "same passphrase to obtain the payload.")
        status = "OK"
    elif "could not extract any data with that passphrase" in text:
        parsed["contains_data"] = None
        parsed["assessment"] = (
            "Carrier is a Steghide-compatible format. The supplied passphrase did "
            "not unlock anything, so either no data is embedded or a different "
            "passphrase is required - this is an observation, not a conclusion.")
        status = "OK"
    else:
        parsed["contains_data"] = False
        parsed["assessment"] = (
            "Steghide found no embedded data in this carrier. Other embedding "
            "methods (LSB, spread spectrum, EOF containers) are unaffected by this "
            "check.")
        status = "OK"
    return _record(AnalysisType.STEGHIDE_INFO, str(target), "steghide", status,
                   parsed["assessment"][:300], parsed, result.elapsed_ms,
                   case_id, evidence_id)


# ---------------------------------------------------------------------- foremost
def foremost(path: Path, output_dir: Path, file_types: str = "all",
             case_id: int | None = None, evidence_id: int | None = None) -> dict:
    target = validate_readable_file(path)
    out = safe_path(output_dir, must_exist=False)
    if not executor.is_available("foremost"):
        return _record(AnalysisType.FOREMOST, str(target), "foremost",
                       Status.UNAVAILABLE,
                       "foremost is not installed (sudo apt install foremost)",
                       {"available": False}, 0.0, case_id, evidence_id)
    out.mkdir(parents=True, exist_ok=True)
    args = ["-i", str(target), "-o", str(out), "-t", file_types, "-q"]
    result = executor.run("foremost", args, case_id=case_id, timeout=600)
    recovered: list[dict] = []
    for found in sorted(out.rglob("*")):
        if found.is_file():
            recovered.append({"path": str(found), "name": found.name,
                              "size": found.stat().st_size})
    audit = out / "audit.txt"
    return _record(AnalysisType.FOREMOST, str(target), "foremost", result.status,
                   f"{len(recovered)} file(s) carved into {out}",
                   {"available": True, "output_dir": str(out),
                    "file_types": file_types, "recovered_count": len(recovered),
                    "recovered": recovered[:300],
                    "audit": audit.read_text(errors="replace")[:2000]
                    if audit.exists() else "",
                    "stderr": result.stderr.strip()[:300],
                    "command": result.command_display()},
                   result.elapsed_ms, case_id, evidence_id)


# ------------------------------------------------------------------------ zsteg
def zsteg(path: Path, case_id: int | None = None,
          evidence_id: int | None = None) -> dict:
    target = validate_readable_file(path)
    if not executor.is_available("zsteg"):
        return _record(AnalysisType.ZSTEG, str(target), "zsteg", Status.UNAVAILABLE,
                       "zsteg is not installed (Ruby gem: sudo gem install zsteg). "
                       "No Debian package exists - result is NOT fabricated.",
                       {"available": False,
                        "install": "sudo gem install zsteg",
                        "alternative": "Use the native LSB analyser in Image "
                                       "Steganography, or binwalk/entropy."},
                       0.0, case_id, evidence_id)
    result = executor.run("zsteg", ["-a", str(target)], case_id=case_id, timeout=300)
    return _record(AnalysisType.ZSTEG, str(target), "zsteg", result.status,
                   f"zsteg completed ({len(result.stdout)} bytes of output)",
                   {"available": True, "output": result.stdout[:8000],
                    "stderr": result.stderr.strip()[:300],
                    "command": result.command_display()},
                   result.elapsed_ms, case_id, evidence_id)


# ----------------------------------------------------------------------- ffprobe
def ffprobe(path: Path, case_id: int | None = None,
            evidence_id: int | None = None) -> dict:
    target = validate_readable_file(path)
    if not executor.is_available("ffprobe"):
        return _record(AnalysisType.FFPROBE, str(target), "ffprobe",
                       Status.UNAVAILABLE, "ffprobe is not installed",
                       {"available": False}, 0.0, case_id, evidence_id)
    result = executor.run("ffprobe", ["-v", "error", "-print_format", "json",
                                      "-show_format", "-show_streams", str(target)],
                          case_id=case_id)
    data: dict = {}
    if result.ok:
        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            data = {"parse_error": "invalid JSON from ffprobe"}
    return _record(AnalysisType.FFPROBE, str(target), "ffprobe", result.status,
                   f"{len(data.get('streams', []))} stream(s)",
                   {"available": True, "data": data,
                    "command": result.command_display()},
                   result.elapsed_ms, case_id, evidence_id)


# ---------------------------------------------------------------------- triage
def triage(path: Path, work_dir: Path | None = None, carve: bool = False,
           case_id: int | None = None, evidence_id: int | None = None) -> dict:
    """Run the standard forensic pipeline over one file (read-only by default)."""
    target = validate_readable_file(path)
    results: dict[str, dict] = {}
    results["file_type"] = file_type(target, case_id, evidence_id)
    results["strings"] = strings(target, case_id=case_id, evidence_id=evidence_id)
    results["entropy"] = entropy(target, case_id=case_id, evidence_id=evidence_id)
    results["metadata"] = _metadata(target, case_id, evidence_id)
    results["binwalk"] = binwalk(target, case_id=case_id, evidence_id=evidence_id)
    results["steghide_info"] = steghide_info(target, case_id=case_id,
                                             evidence_id=evidence_id)
    results["zsteg"] = zsteg(target, case_id=case_id, evidence_id=evidence_id)
    if carve:
        carve_dir = (work_dir or target.parent) / f"carved_{target.stem}"
        results["foremost"] = foremost(target, carve_dir, case_id=case_id,
                                       evidence_id=evidence_id)
    indicators = []
    if results["file_type"].get("mismatch"):
        indicators.append(results["file_type"]["mismatch"])
    if results["strings"].get("interesting"):
        indicators.append(
            f"{len(results['strings']['interesting'])} interesting string(s) found")
    if results["entropy"].get("entropy", 0) >= 7.5:
        indicators.append("High entropy region(s) detected")
    if results["binwalk"].get("rows"):
        indicators.append(
            f"{len(results['binwalk']['rows'])} embedded signature(s) (binwalk)")
    if results["steghide_info"].get("contains_data"):
        indicators.append("Steghide reports embedded data")
    return {"target": str(target), "results": results, "indicators": indicators,
            "assessment": ("Indicators found - each must be corroborated before it "
                           "becomes a finding." if indicators else
                           "No indicator raised by the automated pipeline."),
            "read_only": True}


def _metadata(target: Path, case_id: int | None, evidence_id: int | None) -> dict:
    from app.modules.metadata.service import read as read_metadata

    snapshot = read_metadata(target, case_id=case_id, evidence_id=evidence_id)
    return {"kind": AnalysisType.METADATA, "tool": snapshot.source,
            "status": "OK" if snapshot.available else "FALLBACK",
            "summary": f"{snapshot.count} metadata tags",
            "entries": [e.as_row() for e in snapshot.entries][:400],
            "error": snapshot.error}
