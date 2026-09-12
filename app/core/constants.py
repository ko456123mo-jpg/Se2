"""Centralised constants and enumerations.

Every status label used anywhere in the project is defined here so the
"no ambiguous claims" policy (project rule 78/79) can be enforced mechanically.
"""
from __future__ import annotations

# ---------------------------------------------------------------- status labels
class Status:
    """Implementation status labels (project rule 78).

    Every feature/technique must carry exactly one of these labels.
    """

    IMPLEMENTED = "IMPLEMENTED"                      # native StegoNexus code, working
    INTEGRATED = "INTEGRATED"                        # external tool wired through ToolExecutor
    SIMULATED = "SIMULATED"                          # educational model, not operational
    REFERENCE = "REFERENCE"                          # documented concept, no execution
    OPTIONAL = "OPTIONAL"                            # research/advanced, not core
    UNAVAILABLE = "UNAVAILABLE"                      # tool absent on this host
    REQUIRES_EXTERNAL_TOOL = "REQUIRES EXTERNAL TOOL"


class Severity:
    INFORMATIONAL = "Informational"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"
    ALL = [INFORMATIONAL, LOW, MEDIUM, HIGH, CRITICAL]
    RANK = {INFORMATIONAL: 0, LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4}


class EvidenceKind:
    ORIGINAL = "original"          # immutable source evidence
    WORKING_COPY = "working_copy"  # scratch copy for destructive tests
    DERIVED = "derived"            # produced by an operation (stego file, carve dir)
    EXTRACTED = "extracted"        # payload recovered from a carrier
    ALL = [ORIGINAL, WORKING_COPY, DERIVED, EXTRACTED]


class CaseState:
    OPEN = "Open"
    CLOSED = "Closed"
    ARCHIVED = "Archived"
    ALL = [OPEN, CLOSED, ARCHIVED]


class AnalysisType:
    FILE_TYPE = "file_type"
    STRINGS = "strings"
    METADATA = "metadata"
    BINWALK = "binwalk"
    STEGHIDE_INFO = "steghide_info"
    FOREMOST = "foremost"
    ZSTEG = "zsteg"
    ENTROPY = "entropy"
    FFPROBE = "ffprobe"
    PE = "pe"
    IOC = "ioc"
    NETWORK = "network"
    ALL = [FILE_TYPE, STRINGS, METADATA, BINWALK, STEGHIDE_INFO, FOREMOST,
           ZSTEG, ENTROPY, FFPROBE, PE, IOC, NETWORK]


class Technique:
    """Technique identifiers used across modules, logs and reports."""

    METADATA_READ = "metadata_read"
    METADATA_INJECT = "metadata_inject"
    TEXT_LSB_KEY = "text_lsb_key"
    IMAGE_STEGHIDE = "image_steghide"
    IMAGE_LSB_NATIVE = "image_lsb_native"
    IMAGE_CYBERHIDE = "image_cyberhide"
    AUDIO_LSB = "audio_lsb"
    AUDIO_PHASE = "audio_phase_coding"
    AUDIO_SPREAD = "audio_spread_spectrum"
    AUDIO_METADATA = "audio_metadata"
    VIDEO_LSB = "video_lsb"
    VIDEO_CONTAINER = "video_container_eof"
    VIDEO_SPREAD = "video_spread_spectrum"
    NET_IPV4_ID = "network_ipv4_id"
    NET_UDP = "network_udp"
    MALWARE_STATIC = "malware_static"
    MALWARE_IOC = "malware_ioc"
    MALWARE_EVASION = "malware_evasion"


# ------------------------------------------------------------------- hash names
HASH_ALGORITHMS = ("md5", "sha1", "sha256", "sha512")
PRIMARY_HASH = "sha256"

# ------------------------------------------------------------------- limits
MAX_TOOL_STDOUT_BYTES = 4 * 1024 * 1024        # cap captured tool output
DEFAULT_TOOL_TIMEOUT = 120                      # seconds
HASH_CHUNK_SIZE = 1024 * 1024
MAX_EVIDENCE_BYTES = 4 * 1024 * 1024 * 1024    # 4 GiB guard for evidence import
MAX_INJECT_METADATA_VALUE = 8192

# ------------------------------------------------------------------- magic markers
SNX_TEXT_MAGIC = b"SNX1"          # text LSB framing
SNX_BINARY_MAGIC = b"SNXB"        # image/audio LSB framing
SNX_EOF_MARKER = b"SNXEOF0001"    # video/container EOF hiding marker
SNX_NET_MAGIC = b"SNXNET1"        # network payload framing

DEFAULT_NETWORK_TTL = 64
IPV4_ID_MIN = 1
IPV4_ID_MAX = 65535
