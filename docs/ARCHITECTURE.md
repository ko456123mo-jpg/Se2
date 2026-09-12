# Architecture

## Layout

```
main.py                     entry point (GUI / CLI / diagnostics)
app/
  core/                     config, constants, exceptions, security, logger, models
  storage/                  schema.sql + SQLite database layer (WAL)
  services/                 tool_executor (safe subprocess), tool_health
  steganography/            bitstream, lsb_{text,image,audio}, phase_coding,
                            spread_spectrum, container, video_lsb, video_spread, ordering
  network/                  encoder, packets, sender, interpreter
  forensic/                 entropy, ioc
  malware/                  pe, evasion (defensive analysis)
  modules/<name>/service.py one facade per feature (cases, evidence, findings, logs,
                            reports, metadata, forensics, hashing, extraction,
                            text, image, audio, video, network, malware, settings,
                            dashboard, toolhealth)
  cli/                      interactive text interface
  gui/                      PySide6 application (themes, icons, widgets, workers,
                            dialogs, main_window, views/*)
scripts/                    install / run / diagnostics / seed / demo / smoke-test
resources/                  branding (logos, icon) + app icons
samples/                    benign synthetic media (seed via scripts/seed_samples.py)
tests/                      pytest regression suite
```

## Data flow

Every operation goes through a module `service` facade that: validates inputs
(`app.core.security`), performs the real work (native Python or an external tool via
`ToolExecutor`), records an `extraction`/`analysis` row + an audit `log_action`, and
returns a rich dict. The GUI and CLI are thin clients over the same facades, so the
text interface and the GUI always agree.

## Persistence

SQLite (`data/stegonexus.db`, WAL mode) stores cases, evidence (path + hashes; the bytes
stay on disk under `cases/`), findings, analyses, extractions, reports and logs. The
dashboard is computed entirely from these tables - nothing is hard-coded.

## Safe execution

`ToolExecutor` runs external tools with argument lists (no `shell=True`), per-tool
timeouts and optional path overrides from Settings. Output is captured, size-limited and
returned to the caller; failures surface as typed `StegoNexusError`s with a
user-friendly *Reason / Suggested action* instead of raw tracebacks.

## Async GUI

Long operations run on `QThreadPool` via `app.gui.workers.Runner`; views stay responsive
and results are marshalled back to the UI thread with Qt signals. Screenshots in
`presentation/screenshots/` are produced by `scripts/gui_smoke_test.py`, which builds the
real window on the `offscreen` platform and navigates every view.

## Honesty policy

Each capability returns a `status_label` drawn from a fixed vocabulary (IMPLEMENTED,
INTEGRATED, REFERENCE, EXTERNAL, OPTIONAL, UNAVAILABLE). A capability that is not present
on the host is reported UNAVAILABLE; a third-party format (OpenPuff etc.) is only ever
REFERENCE. The video EOF container is a custom academic format and is explicitly *not*
compatible with any third-party container.
