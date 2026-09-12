"""Interactive text interface.

A terminal front-end over the same module services the GUI uses, so the two always
agree. Every command performs a real operation and prints measured results; unavailable
tools are reported honestly. Type ``help`` at the prompt.
"""
from __future__ import annotations

import shlex
import sys
from pathlib import Path

from app import APP_NAME, __version__
from app.core.exceptions import StegoNexusError
from app.core.logger import get_logger

LOG = get_logger("cli")

HELP = """Commands (arguments in <>):
  health                     live tool-health matrix
  cases                      list cases            | new <title>
  import <path>              import evidence into the active case
  hash <path>                MD5/SHA1/SHA256/SHA512
  compare <a> <b>            MATCH / MISMATCH
  meta <path>                read metadata         | metainj <path> <key=val>... <out>
  triage <path>              full forensic triage
  tool <name> <path>         file|strings|entropy|binwalk|steghide|zsteg|ffprobe
  textcap <cover>            text LSB capacity
  text <cover> <key> <msg>   encode then decode text LSB (roundtrip)
  imagehide <carrier> <secret> <key> <out>   | imageext <stego> <key> <out>
  audiohide <wav> <secret> <key> <out>       | audioext <stego> <out-key> <out>
  videohide <mp4> <secret> <key> <out>       | videoext <stego> <key> <outdir>
  videodetect <stego>
  netprev <payload>          IPv4-ID encoding preview (no traffic)
  netpcap <pcap>             interpret a capture (anomaly != proof)
  malware <path>             defensive static analysis
  report                     generate PDF/HTML/JSON for the active case
  theme [dark|light]         show or set theme
  help | quit
"""


def _active_case() -> int:
    from app.modules.cases import service as cases

    existing = cases.list_cases()
    if existing:
        return existing[0]["id"]
    return cases.create("CLI session", "created by the text interface")["id"]


def _health(_: list[str]) -> None:
    from app.services.tool_health import health

    rows = health.summary()["rows"]
    width = max(len(r["name"]) for r in rows)
    for row in rows:
        state = "AVAILABLE" if row["available"] else "missing"
        print(f"  [{state:<9}] {row['name'].ljust(width)} {row['classification']:<12} "
              f"{row['version'] or row['path'] or ''}")


def _cases(args: list[str]) -> None:
    from app.modules.cases import service as cases

    if args and args[0] == "new":
        case = cases.create(" ".join(args[1:]) or "CLI case")
        print(f"created case #{case['id']} {case['number']}")
        return
    for case in cases.list_cases():
        print(f"  #{case['id']} {case['number']} [{case['status']}] {case['title']}")


def _import(args: list[str]) -> None:
    from app.modules.evidence import service as evidence

    ev = evidence.import_file(_active_case(), Path(args[0]))
    print(f"imported evidence #{ev['id']} {ev['name']} sha256={ev['sha256'][:16]}...")


def _hash(args: list[str]) -> None:
    from app.modules.hashing import service as hashing

    result = hashing.hash_file(Path(args[0]))
    for name in ("md5", "sha1", "sha256", "sha512"):
        print(f"  {name:<7} {result.hashes[name]}")


def _compare(args: list[str]) -> None:
    from app.modules.hashing import service as hashing

    result = hashing.verify(Path(args[0]), Path(args[1]))
    print(f"  {'MATCH' if result['match'] else 'MISMATCH'} - {result['assessment']}")


def _meta(args: list[str]) -> None:
    from app.modules.metadata import service as metadata

    snapshot = metadata.read(Path(args[0]))
    print(f"  source: {snapshot.source} ({len(snapshot.entries)} tags)")
    for entry in snapshot.entries[:25]:
        print(f"    {entry.group}:{entry.tag} = {entry.value}")


def _metainj(args: list[str]) -> None:
    from app.modules.metadata import service as metadata

    source, out = Path(args[0]), Path(args[-1])
    tags = dict(pair.split("=", 1) for pair in args[1:-1])
    result = metadata.inject(source, tags, out)
    print(f"  injected {result['diff']['counts']['added']} tag(s) -> {out}")


def _triage(args: list[str]) -> None:
    from app.modules.forensics import service as forensics

    result = forensics.triage(Path(args[0]))
    for key, value in result["results"].items():
        print(f"  {key:<12} {value.get('status', '')} {value.get('summary', '')}")
    print(f"  indicators: {len(result['indicators'])} | {result['assessment']}")


def _tool(args: list[str]) -> None:
    from app.modules.forensics import service as forensics

    name, path = args[0], Path(args[1])
    func = {"file": forensics.file_type, "strings": forensics.strings,
            "entropy": forensics.entropy, "binwalk": forensics.binwalk,
            "steghide": forensics.steghide_info, "zsteg": forensics.zsteg,
            "ffprobe": forensics.ffprobe}[name]
    result = func(path)
    print(f"  {name}: {result['status']} - {result['summary']}")


def _text(args: list[str]) -> None:
    from app.modules.text import service as text

    cover, key, message = Path(args[0]).read_text(), args[1], " ".join(args[2:])
    hidden = text.hide(cover, message, key)
    extracted = text.extract(hidden["stego_text"], key)
    print(f"  encoded {hidden['payload_bits']} bits "
          f"({hidden['utilisation']:.2%}); decoded match="
          f"{extracted['message'] == message}")


def _textcap(args: list[str]) -> None:
    from app.modules.text import service as text

    cap = text.capacity(Path(args[0]).read_text())
    print(f"  usable_bytes={cap['usable_bytes']} eligible={cap['eligible_chars']}")


def _imagehide(args: list[str]) -> None:
    from app.modules.image import service as image

    result = image.native_embed(Path(args[0]), Path(args[1]), args[2], Path(args[3]), 3)
    print(f"  {result['status']} payload={result['payload_bytes']}B "
          f"verified={result['verified']}")


def _imageext(args: list[str]) -> None:
    from app.modules.image import service as image

    result = image.native_extract(Path(args[0]), args[1], Path(args[2]))
    print(f"  extracted {result['payload_bytes']}B -> {result['output']}")


def _audiohide(args: list[str]) -> None:
    from app.modules.audio import service as audio

    result = audio.lsb_hide(Path(args[0]), Path(args[1]), args[2], Path(args[3]))
    print(f"  {result['status']} payload={result['payload_bytes']}B "
          f"snr={result['snr_db']}dB")


def _audioext(args: list[str]) -> None:
    from app.modules.audio import service as audio

    result = audio.lsb_extract(Path(args[0]), args[1], Path(args[2]))
    print(f"  extracted {result['payload_bytes']}B -> {result['output']}")


def _videohide(args: list[str]) -> None:
    from app.modules.video import service as video

    result = video.container_hide(Path(args[0]), Path(args[1]), args[2], Path(args[3]))
    print(f"  {result['status']} payload={result['payload_bytes']}B "
          f"({result['classification']})")


def _videoext(args: list[str]) -> None:
    from app.modules.video import service as video

    result = video.container_extract(Path(args[0]), args[1], Path(args[2]))
    print(f"  extracted {result['payload_bytes']}B -> {result['output']}")


def _videodetect(args: list[str]) -> None:
    from app.modules.video import service as video

    result = video.container_detect(Path(args[0]))
    print(f"  has_container={result['has_container']} - {result['assessment']}")


def _netprev(args: list[str]) -> None:
    from app.modules.network import service as network

    result = network.encode_preview(" ".join(args).encode())
    print(f"  packets={result['packets']} bits={result['bits']} crc={hex(result['crc'])}")


def _netpcap(args: list[str]) -> None:
    from app.modules.network import service as network

    result = network.analyse_capture(Path(args[0]))
    interp = result["interpretation"]
    print(f"  confidence={interp['confidence']} - {interp['assessment']}")


def _malware(args: list[str]) -> None:
    from app.modules.malware import service as malware

    result = malware.static_analysis(Path(args[0]))
    print(f"  indicators={result['indicator_count']} score={result['heuristic_score']} "
          f"pe={result['pe']['is_pe']}")


def _report(_: list[str]) -> None:
    from app.modules.reports import service as reports

    for row in reports.generate(_active_case()):
        print(f"  {row['format']:<5} {row['path']} ({row['bytes']}B)")


def _theme(args: list[str]) -> None:
    from app.modules.settings import service as settings

    if args:
        settings.save(theme=args[0])
    print(f"  theme={settings.current()['theme']}")


DISPATCH = {
    "health": _health, "cases": _cases, "import": _import, "hash": _hash,
    "compare": _compare, "meta": _meta, "metainj": _metainj, "triage": _triage,
    "tool": _tool, "text": _text, "textcap": _textcap, "imagehide": _imagehide,
    "imageext": _imageext, "audiohide": _audiohide, "audioext": _audioext,
    "videohide": _videohide, "videoext": _videoext, "videodetect": _videodetect,
    "netprev": _netprev, "netpcap": _netpcap, "malware": _malware,
    "report": _report, "theme": _theme,
}


def run_cli(argv: list[str] | None = None) -> int:  # noqa: ARG001 - argv reserved
    print(f"{APP_NAME} {__version__} - interactive text interface (type 'help')")
    while True:
        try:
            line = input("stegonexus> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        try:
            parts = shlex.split(line)
        except ValueError:
            parts = line.split()
        command, args = parts[0], parts[1:]
        if command in ("quit", "exit", "q"):
            return 0
        if command == "help":
            print(HELP)
            continue
        handler = DISPATCH.get(command)
        if handler is None:
            print(f"unknown command '{command}' - type 'help'")
            continue
        try:
            handler(args)
        except StegoNexusError as exc:
            print(f"Operation failed: {exc}")
        except (IndexError, FileNotFoundError) as exc:
            print(f"Bad arguments: {exc} - see 'help'")
        except Exception as exc:  # noqa: BLE001 - keep the REPL alive, log the detail
            LOG.exception("CLI command %s failed", command)
            print(f"Operation failed: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
