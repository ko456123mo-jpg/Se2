# Oral Defense Guide

How to defend StegoNexus in a 5-10 minute examination. Every claim below can be re-run
live; never assert anything the app cannot demonstrate.

## Opening (1 min)

> "StegoNexus is an integrated steganography and digital-forensics workstation. Its rule
> is honesty: every feature carries a status label - IMPLEMENTED, INTEGRATED, REFERENCE,
> EXTERNAL, OPTIONAL or UNAVAILABLE - and nothing is ever simulated as real."

Show the **Dashboard** (computed from the live database) and **Tool Health** (measured
matrix). Point out `14/24 available` and that missing tools read UNAVAILABLE.

## Core techniques (3-4 min)

1. **Text LSB+Key** - encode/decode live; quote the utilisation figure.
   *Q: why is utilisation < 1?* A: one bit per eligible character plus a reserved header.
2. **Image LSB vs Steghide** - native LSB is spatial (lossless carriers); Steghide is a
   transform-domain tool we integrate. *Q: why not use LSB on JPEG?* A: lossy compression
   destroys LSB data.
3. **Audio LSB + phase + spread** - quote the measured SNR. *Q: is it inaudible?* A: we
   report SNR per operation; no blanket imperceptibility claim.
4. **Video EOF container** - explain AES-256-GCM + PBKDF2, appended after an intact
   carrier. *Q: is it OpenPuff-compatible?* A: **No - deliberately.** It is a custom
   academic format.
5. **Network lab** - preview encoding (no traffic), then interpret a pcap.
   *Q: does an anomaly prove hidden data?* A: **No** - indicator, not proof; show the
   teaching text.

## Forensics & reporting (2 min)

Run **full triage** on a file; note binwalk/strings/entropy/foremost/zsteg statuses.
Generate a **report** (PDF/HTML/JSON) and show the embedded hashes + tool snapshot.

## Anticipated hard questions

- *What did you NOT implement?* zsteg (uninstalled Ruby gem), Wireshark/Audacy launchers
  are optional externals, OpenPuff/CyberHide/DeepSound/Coagula are REFERENCE only.
- *How do you prove evidence integrity?* SHA-256 on import; originals never mutated;
  derived artefacts verified with MATCH/MISMATCH.
- *Why no shell=True?* Argument-list execution prevents injection and matches the threat
  model of a forensic tool handling untrusted files.
- *Is the malware module offensive?* No - static, defensive, never executes specimens.

## Closing

> "The point is not that every tool is present; it is that the workbench always tells the
> truth about what it did, what it used, and what it cannot do."
