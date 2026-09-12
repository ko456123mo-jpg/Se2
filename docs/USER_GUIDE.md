# User Guide

This walk-through uses only the synthetic samples in `samples/` so it is safe to repeat.

## 1. Start a case

Open the GUI (`./scripts/run.sh`). Use **+ New Case** (or the Cases view) to create a
case with a title, description and investigator. The active-case selector in the header
switches context for every view.

## 2. Import evidence

In **Evidence**, import `samples/images/carrier_noise.png`. The original is copied into
the case store and hashed (SHA-256 primary). The original file on disk is never mutated.

## 3. Analysis

- **Metadata**: Read metadata (ExifTool). Inject a `Comment`/`Author` into a *copy* and
  verify the before/after hashes differ while the source stays pristine.
- **Forensics**: Select the file and run `file`, `strings`, `entropy`, `binwalk`,
  `steghide info`, `foremost`, `zsteg` (UNAVAILABLE if not installed), or **Run full
  triage** for a combined assessment.
- **Hashing**: Compute MD5/SHA-1/SHA-256/SHA-512 and compare two files (MATCH /
  MISMATCH).

## 4. Steganography

- **Text**: Load a cover, enter a secret and key, then Encode / Decode / Capacity /
  Analyse.
- **Image**: Choose `native-lsb` or `steghide`, pick carrier + secret + password +
  output, Hide, then Extract and verify. `Steghide info` and `LSB analyse` are available.
- **Audio**: Choose `lsb` / `phase` / `spread`. Hide and extract against
  `samples/audio/carrier.wav`. External tools button reports Audacity / DeepSound /
  CoagulaLight honestly.
- **Video**: Choose `lsb` / `container` / `spread` against `samples/video/carrier.mp4`.
  The **container** is the custom academic EOF container (AES-256-GCM); **Detect
  container** and **ffprobe** verify the artefact.

## 5. Network lab (authorized only)

Enable *Authorized laboratory mode* in **Settings** first. **Preview encoding** shows the
IPv4 ID mapping without sending. Send/Receive work on loopback only and require root.
**Analyse pcap** runs the interpreter - remember *an anomaly is an indicator, not proof*.

## 6. Findings, logs, reports

Record a finding from any view or in **Findings**. **Investigation Logs** shows the full
audit trail. **Reports** generates branded PDF/HTML/JSON from real stored records; every
report includes hashes and the tool-health snapshot.

## 7. Extraction Center & Tool Health

**Extraction Center** lists every steganographic operation with its status label.
**Tool Health** re-probes the environment on demand.
