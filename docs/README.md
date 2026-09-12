# StegoNexus Documentation

> Hide it. Extract it. Analyze it. Verify it. Investigate it. Document it. Report it.

StegoNexus is an integrated steganography and digital-forensics investigation
workstation for Kali Linux, built as an academic cybersecurity project. It unifies
text / image / audio / video / network steganography with a case-management,
evidence, findings, logging and reporting pipeline.

This documentation set describes the application *as built*; every capability carries
an honest status label (see [MODULE_STATUS.md](MODULE_STATUS.md)):

| Label | Meaning |
|-------|---------|
| IMPLEMENTED | Native Python code in this repository, tested. |
| INTEGRATED | A real external tool wired through the ToolExecutor, or a real library used. |
| REFERENCE | A third-party application detected and documented, never faked or re-implemented (OpenPuff, CyberHide, DeepSound, CoagulaLight, Audacity). |
| EXTERNAL | A system tool the app can launch (Audacity, Wireshark). |
| OPTIONAL | Enhances the app but is not required. |
| UNAVAILABLE | Not installed on this host; reported honestly, never simulated. |

## Documents

| File | Purpose |
|------|---------|
| [INSTALLATION.md](INSTALLATION.md) | Install on Kali (apt + pip) and launch. |
| [USER_GUIDE.md](USER_GUIDE.md) | How to drive the GUI through a full investigation. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layout, data flow, persistence, async model. |
| [MODULE_STATUS.md](MODULE_STATUS.md) | The full status matrix (tools + techniques). |
| [TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md) | Requirement -> implementation -> test mapping. |
| [SECURITY_AND_ETHICS.md](SECURITY_AND_ETHICS.md) | Authorized-lab and defensive-analysis constraints. |
| [LIMITATIONS.md](LIMITATIONS.md) | Genuine limitations and what is / is not claimed. |
| [ORAL_DEFENSE_GUIDE.md](ORAL_DEFENSE_GUIDE.md) | How to defend the work in an oral examination. |
| [COMPLETION_PLAN.md](COMPLETION_PLAN.md) | Requirement -> state -> files, and the phased plan. |
| [CASE_STUDIES.md](CASE_STUDIES.md) | Synthetic training cases A/B/C (labelled) + swap-in guide. |
| [EXTERNAL_TOOLS_MATRIX.md](EXTERNAL_TOOLS_MATRIX.md) | Course tools detected/documented, never faked. |
| [COMPLETION_REPORT.md](COMPLETION_REPORT.md) | What changed, coverage before/after, verification. |
