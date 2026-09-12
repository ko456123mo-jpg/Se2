# Completion Plan

Living plan produced before/alongside the repair work. Every requirement lists its current
state and the file(s) responsible. Statuses are measured, never assumed.

Legend: COMPLETE / PARTIAL / MISSING / EXTERNAL / UNAVAILABLE.

## Original requirements -> state -> responsible files

| Requirement | State | Files |
|---|---|---|
| PySide6 dashboard + views | COMPLETE | app/gui/main_window.py, app/gui/views/* |
| Cases/Evidence/Findings/Logs/Reports | COMPLETE | app/modules/{cases,evidence,findings,logs,reports}/service.py |
| Metadata read/inject/compare | COMPLETE | app/modules/metadata/service.py, views/metadata_view.py |
| Hashing MD5/SHA1/SHA256/SHA512 | COMPLETE | app/modules/hashing/service.py |
| Text LSB + Key | COMPLETE | app/steganography/lsb_text.py, modules/text |
| Image Native LSB + Steghide | COMPLETE | steganography/lsb_image.py, modules/image |
| Audio LSB/Phase/Spread/Metadata | COMPLETE | lsb_audio/phase_coding/spread_spectrum, modules/audio |
| Video LSB/Spread/EOF container | COMPLETE | video_lsb/video_spread/container, modules/video |
| Network IPv4-ID/UDP/PCAP | COMPLETE | app/network/*, modules/network |
| Malware static defensive | COMPLETE | app/malware/*, modules/malware (+ELF/Office this phase) |
| Forensics file/strings/binwalk/steghide/foremost/zsteg | COMPLETE | modules/forensics/service.py |
| Reports PDF/HTML/JSON | COMPLETE | modules/reports/service.py |
| Synthetic samples | COMPLETE | scripts/seed_samples.py |
| Tests + GUI smoke + demo | COMPLETE | tests/, scripts/{gui_smoke_test,demo_end_to_end}.py |
| Case 1/2/3 original material | MISSING (external) | replaced by labelled synthetic training cases |
| CyberHide/DeepSound/Coagula/OpenPuff/Audacity/Wireshark | EXTERNAL | External Tools Matrix view + EXTERNAL_TOOLS_MATRIX.md |
| zsteg | UNAVAILABLE | reported honestly; gem install documented |

## Execution plan (priority order)

1. P1 Analysis & plan (this file) - DONE.
2. P2 Synthetic training cases (A/B/C) + fixtures + per-case tests + CASE_STUDIES.md.
3. P3 Metadata UI: full tag set + tag-level Before/After + audio/video metadata tests.
4. P4 External Tools Matrix view + EXTERNAL_TOOLS_MATRIX.md (no fake integration).
5. P5 Network: local encode/decode reassembly test + UI pre-send authorization warning.
6. P6 Malware: safe ELF + Office static analysis + confidence reporting + tests.
7. P7 Installer idempotence + dependency checks (already idempotent; verified).
8. P8 Expand test-suite (below) with honest skip/UNAVAILABLE handling.
9. P9 Docs (CASE_STUDIES, EXTERNAL_TOOLS_MATRIX, COMPLETION_REPORT) + presentation.
10. P10 Verification artefacts + FINAL_AUDIT/TRACEABILITY update + final summary.

## Dependencies
See requirements.txt + scripts/install_kali.sh. All required libs present; optional tools
degrade gracefully.

## Risks & constraints
- Never fabricate results; label synthetic cases clearly.
- Network lab loopback/RFC1918 + authorized switch + root only.
- Malware static only; no execution/sandbox/persistence/credential/injection/bypass.
- Read-only evidence; originals never mutated.
- No shell=True; argument-list execution with timeouts.
