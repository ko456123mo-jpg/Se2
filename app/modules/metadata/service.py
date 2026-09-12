"""Metadata analysis & injection service (project rule 12).

Primary tool: **ExifTool**.  When ExifTool is not installed the service falls
back to a pure-Python reader (Pillow for images, FFprobe for audio/video) and
labels the result accordingly - it never pretends to have run ExifTool.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.core.constants import Status
from app.core.exceptions import ToolUnavailable, UnsupportedFormat, ValidationError
from app.core.logger import log_event
from app.core.models import MetadataEntry, MetadataSnapshot
from app.core.security import validate_metadata_value, validate_output_path, validate_readable_file
from app.modules.hashing.service import hash_file
from app.services.tool_executor import executor
from app.storage.database import get_db

#: tags the GUI offers for controlled injection
INJECTABLE_TAGS = {
    "Comment": "Comment", "Author": "Author", "Title": "Title",
    "Description": "ImageDescription", "Keywords": "Keywords",
    "Artist": "Artist", "Copyright": "Copyright", "Software": "Software",
}


def is_available() -> bool:
    return executor.is_available("exiftool")


def read(path: Path, case_id: int | None = None,
         evidence_id: int | None = None) -> MetadataSnapshot:
    """Read metadata with ExifTool (or the documented fallback)."""
    target = validate_readable_file(path)
    hashes = hash_file(target, algorithms=("sha256",), case_id=case_id,
                       evidence_id=evidence_id).hashes
    if is_available():
        result = executor.run("exiftool", ["-j", "-G", "-api", "LargeFileSupport=1",
                                          str(target)], case_id=case_id)
        if result.ok:
            try:
                payload = json.loads(result.stdout or "[]")
            except json.JSONDecodeError as exc:
                snapshot = MetadataSnapshot(path=str(target), source="exiftool",
                                            available=True, hashes=hashes,
                                            error=f"bad exiftool JSON: {exc}")
                _record(snapshot, case_id, evidence_id)
                return snapshot
            entries = []
            for item in payload[0].items() if payload else []:
                key, value = item
                group, _, tag = key.partition(":")
                if tag == "":
                    group, tag = "File", key
                entries.append(MetadataEntry(group=group, tag=tag,
                                             value=str(value)))
            snapshot = MetadataSnapshot(path=str(target), source="exiftool",
                                        available=True, entries=entries,
                                        hashes=hashes)
            _record(snapshot, case_id, evidence_id)
            return snapshot
        error = result.error or result.stderr.strip()[:300]
    else:
        error = "exiftool not installed"

    snapshot = _fallback_read(target, hashes, error)
    _record(snapshot, case_id, evidence_id)
    return snapshot


def _fallback_read(target: Path, hashes: dict, reason: str) -> MetadataSnapshot:
    """Pure-Python metadata reader used when ExifTool is unavailable."""
    entries = [MetadataEntry("Fallback", "Reason", reason)]
    stat = target.stat()
    entries += [MetadataEntry("File", "FileName", target.name),
                MetadataEntry("File", "FileSize", str(stat.st_size)),
                MetadataEntry("File", "FileModifyTime", str(stat.st_mtime))]
    source = "fallback"
    suffix = target.suffix.lower()
    try:
        if suffix in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp"):
            from PIL import Image
            from PIL.ExifTags import TAGS

            with Image.open(target) as image:
                entries.append(MetadataEntry("File", "Format", image.format or "?"))
                entries.append(MetadataEntry("Image", "Width", str(image.width)))
                entries.append(MetadataEntry("Image", "Height", str(image.height)))
                entries.append(MetadataEntry("Image", "Mode", image.mode))
                exif = image.getexif()
                for tag_id, value in exif.items():
                    entries.append(MetadataEntry("EXIF", TAGS.get(tag_id, str(tag_id)),
                                                 str(value)[:300]))
            source = "pillow-fallback"
        elif suffix in (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".mkv", ".mp4", ".avi"):
            if executor.is_available("ffprobe"):
                result = executor.run("ffprobe", ["-v", "error", "-print_format", "json",
                                                  "-show_format", "-show_streams",
                                                  str(target)])
                data = json.loads(result.stdout or "{}")
                for key, value in (data.get("format", {}).get("tags", {}) or {}).items():
                    entries.append(MetadataEntry("Format", key, str(value)))
                entries.append(MetadataEntry(
                    "Format", "Duration", str(data.get("format", {}).get("duration", ""))))
                source = "ffprobe-fallback"
    except Exception as exc:  # pragma: no cover - defensive
        entries.append(MetadataEntry("Fallback", "Error", str(exc)[:200]))
    return MetadataSnapshot(path=str(target), source=source, available=False,
                            entries=entries, hashes=hashes,
                            error=f"ExifTool unavailable ({reason}); limited "
                                  f"fallback reader used")


def inject(source: Path, tags: dict[str, str], output: Path,
           case_id: int | None = None, evidence_id: int | None = None) -> dict:
    """Write metadata into a **copy** - the original evidence is never modified."""
    src = validate_readable_file(source)
    dest = validate_output_path(output, overwrite=True)
    if not tags:
        raise ValidationError("No metadata tags supplied.")
    clean: dict[str, str] = {}
    for label, value in tags.items():
        tag = INJECTABLE_TAGS.get(label, label)
        clean[tag] = validate_metadata_value(value, label)
    if not is_available():
        raise ToolUnavailable(
            "Metadata injection requires ExifTool (sudo apt install "
            "libimage-exiftool-perl). The fallback reader is read-only.")

    import shutil

    shutil.copy2(src, dest)
    before = read(dest, case_id=case_id, evidence_id=evidence_id)
    args = ["-overwrite_original"]
    for tag, value in clean.items():
        args.append(f"-{tag}={value}")
    args.append(str(dest))
    result = executor.run("exiftool", args, case_id=case_id)
    if not result.ok:
        raise UnsupportedFormat(
            f"ExifTool could not write the metadata: "
            f"{result.error or result.stderr.strip()[:300]}")
    after = read(dest, case_id=case_id, evidence_id=evidence_id)
    before_hashes = hash_file(src, algorithms=("sha256",))
    after_hashes = hash_file(dest, algorithms=("sha256",))
    diff = compare(before, after)
    db = get_db()
    db.log_action(action="Metadata Modified", module="metadata", target=str(dest),
                  case_id=case_id, evidence_id=evidence_id, tool="exiftool",
                  result=f"{len(clean)} tag(s) written", status="OK",
                  hash_value=after_hashes.sha256)
    log_event("metadata", "inject", f"{len(clean)} tags -> {dest.name}",
              case_id=case_id, tool="exiftool")
    return {
        "technique": "metadata_inject", "status": Status.INTEGRATED,
        "original": str(src), "output": str(dest), "tags_written": clean,
        "original_sha256": before_hashes.sha256, "output_sha256": after_hashes.sha256,
        "before": before, "after": after, "diff": diff,
        "note": "The original file was copied before modification; original evidence "
                "remains untouched.",
    }


def strip(source: Path, output: Path, case_id: int | None = None) -> dict:
    """Remove all metadata from a copy (ExifTool ``-all=``)."""
    src = validate_readable_file(source)
    dest = validate_output_path(output, overwrite=True)
    if not is_available():
        raise ToolUnavailable("Metadata stripping requires ExifTool.")
    import shutil

    shutil.copy2(src, dest)
    result = executor.run("exiftool", ["-overwrite_original", "-all=", str(dest)],
                          case_id=case_id)
    if not result.ok:
        raise UnsupportedFormat(f"ExifTool failed: {result.stderr.strip()[:300]}")
    after = read(dest, case_id=case_id)
    get_db().log_action(action="Metadata Stripped", module="metadata", target=str(dest),
                        case_id=case_id, tool="exiftool", result="all tags removed")
    return {"technique": "metadata_strip", "status": Status.INTEGRATED,
            "original": str(src), "output": str(dest), "after": after,
            "tags_remaining": after.count}


def compare(before: MetadataSnapshot, after: MetadataSnapshot) -> dict:
    """Tag-level before/after diff."""
    b = {(e.group, e.tag): e.value for e in before.entries}
    a = {(e.group, e.tag): e.value for e in after.entries}
    added = {k: v for k, v in a.items() if k not in b}
    removed = {k: v for k, v in b.items() if k not in a}
    changed = {k: {"before": b[k], "after": a[k]} for k in a.keys() & b.keys()
               if a[k] != b[k]}
    return {"added": {f"{g}:{t}": v for (g, t), v in added.items()},
            "removed": {f"{g}:{t}": v for (g, t), v in removed.items()},
            "changed": {f"{g}:{t}": v for (g, t), v in changed.items()},
            "counts": {"before": before.count, "after": after.count,
                       "added": len(added), "removed": len(removed),
                       "changed": len(changed)}}


def _record(snapshot: MetadataSnapshot, case_id: int | None,
            evidence_id: int | None) -> None:
    db = get_db()
    db.add_metadata_snapshot({
        "case_id": case_id, "evidence_id": evidence_id, "path": snapshot.path,
        "source": snapshot.source, "available": snapshot.available,
        "entries": [e.as_row() for e in snapshot.entries],
        "hashes": snapshot.hashes, "error": snapshot.error})
    db.log_action(action="Metadata Read", module="metadata", target=snapshot.path,
                  case_id=case_id, evidence_id=evidence_id, tool=snapshot.source,
                  result=f"{snapshot.count} tags",
                  status="OK" if snapshot.available else "FALLBACK",
                  hash_value=snapshot.hashes.get("sha256", ""))
    log_event("metadata", "read", f"{snapshot.count} tags from "
                                  f"{Path(snapshot.path).name}",
              case_id=case_id, tool=snapshot.source,
              status="OK" if snapshot.available else "FALLBACK")
