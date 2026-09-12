# Security & Ethics Constraints

StegoNexus is an educational defensive-security tool. The following constraints are
enforced in code, not just in prose.

## Authorized laboratory (network)

- Transmission and capture are disabled until **Settings > Authorized laboratory mode**
  is enabled; otherwise `send()` raises `AuthorizationError`.
- Address space is restricted to loopback / RFC 1918. Packet injection requires
  elevated privileges, so a normal user cannot transmit.
- The interpreter is explicitly framed as *indicator, not proof*: it returns an
  assessment plus a "why an anomaly is not proof" teaching block.

## Defensive-only malware analysis

- `malware.static_analysis` performs **no execution**. It computes hashes, inspects PE
  headers, extracts IOCs, and detects masquerading / timestomping / obfuscation and
  PyInstaller or archive packaging - purely from bytes on disk.
- The executable-steganography feature (PE overlay / slack-space hide & extract) is a
  byte-level demonstration on **synthetic training carriers and working copies**. It
  exists so the technique can be taught, detected and reversed in a lab; the carrier is
  never run, and every hide operation records the original SHA-256 to prove the source
  was untouched.
- There is no credential access, persistence, injection, UAC/AMSI bypass, or destructive
  behaviour anywhere in the module. `simulate()` only demonstrates evasion *concepts* on
  synthetic working copies in an isolated directory.

## Read-only evidence handling

- `read_only_analysis` defaults to on. Evidence originals are copied into the case store
  and hashed; all transformations (metadata injection, stego embedding, carving) write to
  new derived files. The source bytes are never overwritten.

## Safe process execution

- `ToolExecutor` never uses `shell=True`. Tools are invoked with argument lists, bounded
  by per-tool timeouts, and their output is captured and size-limited.

## User-facing honesty

- Errors are shown as *Operation failed / Reason / Suggested action*; full tracebacks go
  to `logs/stegonexus.log`, never to the user.
- Unavailable tools are reported **UNAVAILABLE**; reference applications are **REFERENCE**.
  No result is ever fabricated, simulated-as-real, or attributed to a tool that is not
  present.
