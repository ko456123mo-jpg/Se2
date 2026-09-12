# Case Studies (Synthetic Training Cases)

> **IMPORTANT:** The three cases below are **TRAINING CASE - SYNTHETIC DATA**. They are
> reproducible educational fixtures created by `scripts/seed_case_fixtures.py`; they are
> **NOT** the course's original Case 1/2/3. To reproduce the original cases, import the
> genuine case files through the GUI/CLI - no code change is required (see "Swapping in
> original material").

Each case records, in the database: number/title/description, educational goal, input
files, media type, hide/extract technique, tool/algorithm, key, before/after hashes,
execution steps (audit log), expected vs. actual result, produced evidence, a timeline,
PDF/HTML/JSON reports and a verification status.

## Case A - Metadata + Image Steganography
- **Goal:** show evidence intake, metadata injection on a copy, and lossless LSB recovery.
- **Inputs:** `samples/images/carrier_noise.png`, `samples/text/secret.txt`.
- **Media:** PNG image. **Technique:** native image LSB (+ ExifTool metadata).
- **Key:** `caseA-key`.
- **Measured result:** 3 metadata tags added to the copy; 38-byte payload hidden;
  SHA-256 of recovered secret **matches** the original (verified=True). Original carrier
  hash unchanged.
- **Evidence:** original carrier + derived stego image registered with hashes.

## Case B - Audio LSB
- **Goal:** demonstrate lossless audio LSB with a measured SNR.
- **Inputs:** `samples/audio/carrier.wav`, `samples/text/secret.txt`. **Key:** `caseB-key`.
- **Measured result:** SNR ~97 dB; recovered secret SHA-256 **matches** (verified=True).

## Case C - Network PCAP + Malware Static
- **Goal:** interpret a covert capture (indicator, not proof) and run defensive static analysis.
- **Inputs:** `samples/network/covert_lab.pcap`, `samples/malware/benign_note.txt`.
- **Measured result:** interpreter confidence **High** on the covert capture; benign
  specimen yields 0 indicators (static, defensive, nothing executed).

## Case D - Executable (malware-carrier) Steganography
- **Goal:** demonstrate the malware-hiding topic end-to-end and its detection:
  hide a payload inside a synthetic PE carrier (overlay or slack space), then
  recover it and flag it statically - nothing is ever executed.
- **Inputs:** `samples/malware/training_carrier.exe` (headers + padded section,
  no code), `samples/text/secret.txt`.
- **Technique:** `overlay` (blob appended after the last PE section) and
  `slack` (blob written into section padding; output keeps the exact carrier size).
- **Key:** `caseD-key`.
- **Measured result:** recovered secret SHA-256 **matches** (verified=True);
  slack output size == carrier size; `Scan hidden data` finds the blob;
  `Static analysis` adds an **Executable stego** indicator for it.

## Swapping in original material
1. Keep the synthetic fixtures as the regression baseline.
2. For a real case, use **Cases > + New Case**, then **Evidence > Import** the genuine file.
3. Run the same views (Metadata / Steganography / Network / Malware) - the services are
   format-agnostic, so no code change is needed.
4. Do **not** rename synthetic cases to Case 1/2/3; keep the labels honest.

Re-create fixtures anytime: `QT_QPA_PLATFORM=offscreen python scripts/seed_case_fixtures.py`.
