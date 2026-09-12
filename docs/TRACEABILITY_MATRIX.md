# Traceability Matrix

Requirement -> implementation -> verification.

| # | Requirement | Implementation | Verified by |
|---|-------------|----------------|-------------|
| 1 | Text stego LSB+Key | `app/steganography/lsb_text.py`, `app/modules/text/service.py` | `tests/test_stego_roundtrips.py` |
| 2 | Image native LSB + Steghide | `lsb_image.py`, `image/service.py` | roundtrip test; demo step |
| 3 | Audio LSB/phase/spread + metadata | `lsb_audio/phase_coding/spread_spectrum`, `audio/service.py` | roundtrip test |
| 4 | Video FFV1 LSB + custom EOF container + spread | `video_lsb/container/video_spread`, `video/service.py` | container roundtrip+tamper test |
| 5 | Network lab + interpreter (anomaly != proof) | `network/*`, `network/service.py` | `test_network_metadata_malware.py` |
| 6 | Defensive malware analysis | `malware/*`, `malware/service.py` | malware test |
| 7 | Cases / evidence immutability | `cases|evidence/service.py` | metadata test (source hash unchanged) |
| 8 | Hashing MD5/SHA1/SHA256/SHA512 + MATCH/MISMATCH | `hashing/service.py` | `test_hashing.py` |
| 9 | Metadata read/inject/strip/compare + hashes | `metadata/service.py` (exiftool) | metadata test |
| 10 | Forensics toolchain + triage | `forensics/service.py` | demo + Tool Health |
| 11 | Branded reports PDF/HTML/JSON | `reports/service.py` (QPdfWriter from QtGui) | `test_reports_health.py` |
| 12 | Dynamic Tool Health | `services/tool_health.py` | tool-health test + view |
| 13 | Safe execution (no shell) | `services/tool_executor.py` | code + all tool tests |
| 14 | PySide6 GUI (sidebar, dashboard, tables, dialogs, themes, async) | `app/gui/*` | `scripts/gui_smoke_test.py` (19/19 + screenshots) |
| 15 | End-to-end demonstration | `scripts/demo_end_to_end.py` | 14/14 steps pass |
| 16 | Benign synthetic samples | `scripts/seed_samples.py` | seeded into `samples/` |
| 17 | Honest statuses (never fabricated) | status_label vocabulary across services | LIMITATIONS.md + UI chips |
| 18 | Synthetic training cases A/B/C (labelled SYNTHETIC) | scripts/seed_case_fixtures.py | tests/test_training_cases.py |
| 19 | External Tools Matrix (no fake integration) | views/external_tools_view.py + EXTERNAL_TOOLS_MATRIX.md | gui smoke 20/20 |
| 20 | Malware ELF/Office static + correlation confidence | malware/service.py | tests/test_network_metadata_malware.py |
| 21 | Network local reassembly + pre-send auth warning | network/* + views/network_view.py | roundtrip test + UI dialog |
| 22 | Metadata full tag set + tag-level Before/After | metadata/service.py + views/metadata_view.py | tests/test_metadata_media.py |

The oral defense should walk this matrix top-to-bottom; every row can be re-run live.
