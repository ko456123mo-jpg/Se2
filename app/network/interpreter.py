"""Forensic interpretation layer for network observations.

Project rule 40 in code form.  An unusual IPv4 Identification field is an
**observation**, not a conclusion.  This module walks the mandatory chain

    observation -> indicator -> context -> correlation -> assessment

and refuses to emit "steganography confirmed" unless there is corroborating
evidence (for example a payload that actually reassembles and verifies).
"""
from __future__ import annotations

import math
from collections import Counter

from app.core.models import PacketAnalysis
from app.network import encoder

#: Legitimate explanations that must always be presented next to an anomaly.
LEGITIMATE_EXPLANATIONS = [
    "Operating-system behaviour: Linux uses a global incrementing counter, some "
    "BSD/Windows stacks randomise the Identification field by design.",
    "IP fragmentation and reassembly: fragments of one datagram share an id, and "
    "heavily fragmented traffic distorts the distribution.",
    "Network equipment: NAT gateways, load balancers and middleboxes rewrite ids.",
    "Packet generators and libraries (Scapy, hping3, custom agents) often produce "
    "sequential or randomised ids.",
    "Sampling artefacts: a short capture window or a filtered view can look random.",
    "Privacy extensions / anti-fingerprinting features deliberately randomise ids.",
]


def entropy_bits(values: list[int], width: int = 16) -> float:
    """Shannon entropy (bits) of the observed field values."""
    if not values:
        return 0.0
    counts = Counter(values)
    total = len(values)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def id_field_statistics(ip_ids: list[int]) -> dict:
    """Distribution facts about a sequence of IPv4 Identification values."""
    if not ip_ids:
        return {"count": 0}
    deltas = [b - a for a, b in zip(ip_ids, ip_ids[1:])]
    incrementing = sum(1 for d in deltas if d == 1)
    repeated = sum(1 for d in deltas if d == 0)
    unique = len(set(ip_ids))
    zeros = sum(1 for v in ip_ids if v == 0)
    return {
        "count": len(ip_ids),
        "unique": unique,
        "unique_ratio": round(unique / len(ip_ids), 4),
        "entropy_bits": round(entropy_bits(ip_ids), 4),
        "entropy_ratio": round(entropy_bits(ip_ids) / 16, 4),
        "incrementing_pairs": incrementing,
        "incrementing_ratio": round(incrementing / max(1, len(deltas)), 4),
        "repeated_pairs": repeated,
        "repeated_ratio": round(repeated / max(1, len(deltas)), 4),
        "zero_ids": zeros,
        "min": min(ip_ids),
        "max": max(ip_ids),
        "mean": round(sum(ip_ids) / len(ip_ids), 2),
    }


def channel_statistics(packets: list[dict]) -> dict:
    """Traffic-level facts (ports, payload lengths) used for context."""
    if not packets:
        return {"count": 0}
    dports = Counter(p.get("dport") for p in packets if p.get("dport") is not None)
    sports = Counter(p.get("sport") for p in packets if p.get("sport") is not None)
    lengths = [p.get("payload_len", 0) for p in packets]
    empty = sum(1 for ln in lengths if ln == 0)
    return {
        "count": len(packets),
        "distinct_dports": len(dports),
        "top_dports": dports.most_common(5),
        "distinct_sports": len(sports),
        "empty_payload_packets": empty,
        "empty_payload_ratio": round(empty / len(packets), 4),
        "mean_payload_len": round(sum(lengths) / len(packets), 2),
        "protocols": dict(Counter(p.get("proto", "?") for p in packets)),
    }


def attempt_extraction(ip_ids: list[int]) -> dict:
    """Try to reassemble a StegoNexus covert payload (corroborating evidence)."""
    try:
        payload, info = encoder.decode(ip_ids)
        return {"reassembled": True, "payload_bytes": len(payload),
                "preview": payload[:64].decode("utf-8", errors="replace"), **info}
    except Exception as exc:
        return {"reassembled": False, "reason": f"{type(exc).__name__}: {exc}"}


def interpret(packets: list[dict], ip_ids: list[int] | None = None) -> PacketAnalysis:
    """Run the observation -> assessment chain over captured packets."""
    ids = ip_ids if ip_ids is not None else [p["ip_id"] for p in packets
                                             if p.get("ip_id") is not None]
    stats = id_field_statistics(ids)
    channel = channel_statistics(packets)
    extraction = attempt_extraction(ids) if ids else {"reassembled": False,
                                                      "reason": "no IPv4 ids"}

    observation = (
        f"{stats.get('count', 0)} packets examined; "
        f"{stats.get('unique', 0)} distinct IPv4 Identification values; "
        f"entropy {stats.get('entropy_bits', 0)} bits "
        f"({round(100 * stats.get('entropy_ratio', 0), 1)}% of the 16-bit maximum); "
        f"{round(100 * stats.get('incrementing_ratio', 0), 1)}% of consecutive pairs "
        f"increment by exactly 1; "
        f"{round(100 * channel.get('empty_payload_ratio', 0), 1)}% of packets carry an "
        f"empty UDP payload.")

    indicators: list[str] = []
    # An indicator is only reported when it is genuinely atypical.  A single
    # destination port is normal for any session and is therefore only used to
    # *strengthen* a primary indicator, never on its own.
    id_random = (stats.get("entropy_ratio", 0) > 0.9
                 and stats.get("incrementing_ratio", 0) < 0.05)
    header_only = (channel.get("empty_payload_ratio", 0) > 0.8
                   and stats.get("count", 0) > 20)
    if id_random:
        indicators.append("Identification field is near-uniform with no OS increment "
                          "pattern (consistent with randomisation OR embedding).")
    if header_only:
        indicators.append("Many small packets with empty payloads - a header-only "
                          "channel shape.")
    if (id_random or header_only) and stats.get("count", 0) >= 20 \
            and channel.get("distinct_dports", 0) <= 2:
        indicators.append("Traffic is concentrated on a single destination port.")
    if not indicators:
        indicators.append("No structural indicator of header embedding was observed.")

    context = list(LEGITIMATE_EXPLANATIONS)

    correlation = []
    if extraction.get("reassembled"):
        correlation.append(
            f"Strong corroboration: the Identification values reassemble into a valid "
            f"StegoNexus payload ({extraction.get('payload_bytes')} bytes, CRC-32 "
            f"verified): {extraction.get('preview')!r}")
    else:
        correlation.append(
            "No verifiable payload could be reassembled from the Identification "
            f"values ({extraction.get('reason', 'n/a')}).")
    correlation.append(
        "Still required for a defensible conclusion: endpoint attribution, timeline "
        "correlation with host artefacts, repeated observations across sessions, and "
        "an explanation that excludes the legitimate causes listed above.")

    if extraction.get("reassembled"):
        assessment = ("Covert-channel activity CONFIRMED: a structured, CRC-verified "
                      "payload was recovered from the IPv4 Identification field. The "
                      "statistical anomaly is corroborated by content recovery.")
        confidence = "High"
    elif not indicators[-1].startswith("No structural"):
        assessment = ("Suspicious pattern requiring investigation: the Identification "
                      "field distribution is atypical, but the legitimate explanations "
                      "listed above have NOT been excluded and no payload could be "
                      "recovered. An anomaly is an indicator, never proof of "
                      "steganography.")
        confidence = "Low"
    else:
        assessment = ("No indication of header steganography in this capture. Absence "
                      "of indicators does not prove the channel is clean.")
        confidence = "Low"

    return PacketAnalysis(observation=observation,
                          indicator="; ".join(indicators),
                          context=context, correlation=correlation,
                          assessment=assessment, confidence=confidence,
                          packets_examined=len(packets))


def explain_why_anomaly_is_not_proof() -> str:
    """Teaching text reused by the GUI, the manual and the oral-exam guide."""
    return (
        "An unusual IPv4 Identification field alone does NOT prove steganography. "
        "Operating systems differ: Linux increments a global counter, while several "
        "BSD and Windows stacks randomise the field. Fragmentation makes ids repeat, "
        "NAT devices rewrite them, and privacy features randomise them on purpose. "
        "A defensible finding therefore requires the full chain - observation, "
        "indicator, context, correlation and an assessment that explicitly excludes "
        "the legitimate explanations. Recovering a structured payload from the field "
        "is what turns an indicator into evidence.")
