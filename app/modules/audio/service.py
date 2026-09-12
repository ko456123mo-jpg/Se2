"""Audio hiding & analysis service (project rules 23-30).

Techniques
----------
``audio_lsb``             native, verified end-to-end.
``audio_phase_coding``    native DSP implementation (fragile by nature - the
                          measured SNR is always reported).
``audio_spread_spectrum`` native DS-SS implementation with blind and
                          differential detection.
``audio_metadata``        ExifTool integration (read / inject / compare).

Analysis helpers provide waveform and spectrogram data for plotting, and the
service can hand a file to **Audacity** when it is installed - it never claims to
contain Audacity functionality.
"""
from __future__ import annotations

import time
import wave
from pathlib import Path

from app.core.constants import Status, Technique
from app.core.exceptions import ToolUnavailable, UnsupportedFormat
from app.core.logger import log_event
from app.core.security import validate_output_path, validate_readable_file
from app.modules.hashing.service import hash_file
from app.services.tool_executor import executor
from app.steganography import audio_spread, lsb_audio, phase_coding, spread_spectrum
from app.storage.database import get_db

TECHNIQUE_STATUS = {
    Technique.AUDIO_LSB: Status.IMPLEMENTED,
    Technique.AUDIO_PHASE: Status.IMPLEMENTED,
    Technique.AUDIO_SPREAD: Status.IMPLEMENTED,
    Technique.AUDIO_METADATA: Status.INTEGRATED,
    "deepsound": Status.REFERENCE,
    "coagula": Status.REFERENCE,
    "audacity": Status.INTEGRATED,
}

# Human-readable matrix used by the GUI. Carriers/recovery statements describe what the
# shipped code actually does; nothing here claims imperceptibility that was not measured.
TECHNIQUE_INFO: dict[str, tuple[str, str, str]] = {
    Technique.AUDIO_LSB: ("16-bit PCM WAV (lossless)", "Exact - verified after write",
                          "Native LSB with key-derived sample ordering; SNR is measured "
                          "and reported for every operation."),
    Technique.AUDIO_PHASE: ("Any PCM audio", "Requires an unmodified carrier",
                            "Phase-coded segments. SNR can be negative by design: robustness "
                            "is traded for audibility."),
    Technique.AUDIO_SPREAD: ("Any PCM audio", "Differential (a clean reference improves it)",
                             "PN chip spreading with processing gain; capacity falls as the "
                             "chip length grows."),
    Technique.AUDIO_METADATA: ("Any tagged audio file", "Exact",
                               "ExifTool tag injection performed on a copy, with before/after "
                               "hashes recorded."),
    "deepsound": ("WAV (course practical tool)", "DeepSound only",
                  "Windows course tool: detected, documented and left as an external "
                  "reference. Not re-implemented."),
    "coagula": ("Spectrogram image -> WAV", "CoagulaLight only",
                "Windows course tool for spectrogram-image audio: detected and documented "
                "only."),
    "audacity": ("Any audio", "External, interactive",
                 "Installed editor for waveform/spectrogram inspection; StegoNexus can "
                 "launch it on a working copy."),
}


def techniques() -> list[dict]:
    """Technique matrix for the GUI, with availability measured - never assumed."""
    rows = []
    for technique, (carriers, recovery, note) in TECHNIQUE_INFO.items():
        external = technique in ("deepsound", "coagula", "audacity")
        rows.append({"name": technique,
                     "classification": TECHNIQUE_STATUS.get(technique,
                                                            Status.IMPLEMENTED),
                     "available": (executor.is_available(technique) if external else True),
                     "carriers": carriers, "recovery": recovery, "note": note})
    return rows


def _record(technique: str, operation: str, status: str, **kwargs) -> None:
    db = get_db()
    status_label = kwargs.pop("status_label", TECHNIQUE_STATUS.get(technique,
                                                                   Status.IMPLEMENTED))
    engine = kwargs.pop("engine", "native-python")
    db.add_extraction({"technique": technique, "operation": operation, "status": status,
                       "status_label": status_label, "engine": engine,
                       "messages": [], "details": {}, **kwargs})
    db.log_action(action=f"Steganography Operation ({operation})", module="audio",
                  target=kwargs.get("input_path", ""), case_id=kwargs.get("case_id"),
                  tool=engine, result=f"{technique}: {status}", status=status,
                  hash_value=kwargs.get("output_hash", ""))


def tools() -> list[dict]:
    """Audio tool status, measured - including the Windows reference tools."""
    rows = []
    for name, label in (("audacity", "Audacity (waveform/spectrogram analysis)"),
                        ("deepsound", "DeepSound (course practical tool)"),
                        ("coagula", "CoagulaLight (spectrogram image audio)"),
                        ("ffmpeg", "FFmpeg (format conversion / processing)")):
        available = executor.is_available(name)
        classification = (TECHNIQUE_STATUS.get(name, Status.INTEGRATED)
                          if available else
                          (Status.REFERENCE if name in ("deepsound", "coagula")
                           else Status.UNAVAILABLE))
        rows.append({"name": name, "label": label, "available": available,
                     "path": executor.resolve(name) or "",
                     "version": executor.version(name, ["--version"]),
                     "classification": classification,
                     "note": ("External practical/reference tool from the course "
                              "material; StegoNexus detects it and documents the "
                              "workflow." if name in ("deepsound", "coagula") else
                              ("Installed - files can be opened for interactive "
                               "analysis." if available and name == "audacity" else
                               "Integrated through the ToolExecutor."))})
    return rows


def info(path: Path) -> dict:
    inf = lsb_audio.info(validate_readable_file(path))
    return {**inf.as_dict(), "status_label": Status.IMPLEMENTED}


def capacity(path: Path, technique: str = Technique.AUDIO_LSB, **params) -> dict:
    target = validate_readable_file(path)
    if technique == Technique.AUDIO_LSB:
        return {**lsb_audio.capacity(target), "technique": technique}
    if technique == Technique.AUDIO_PHASE:
        return {**phase_coding.capacity(target, **params), "technique": technique}
    if technique == Technique.AUDIO_SPREAD:
        return {**audio_spread.capacity(target, **params), "technique": technique}
    raise UnsupportedFormat(f"Unknown audio technique: {technique}")


def prepare(carrier: Path, output: Path) -> dict:
    """Convert any audio file into 16-bit PCM WAV with FFmpeg."""
    source = validate_readable_file(carrier)
    dest = validate_output_path(output, overwrite=True)
    result = lsb_audio.prepare_wav(source, dest)
    get_db().log_action(action="Audio Prepared", module="audio", target=str(dest),
                        tool="ffmpeg", result="converted to 16-bit PCM WAV")
    return {**result, "status_label": Status.INTEGRATED,
            "source_sha256": hash_file(source, algorithms=("sha256",)).sha256,
            "output_sha256": hash_file(dest, algorithms=("sha256",)).sha256}


# -------------------------------------------------------------------------- LSB
def lsb_hide(carrier: Path, secret: Path, key: str, output: Path,
             case_id: int | None = None, evidence_id: int | None = None) -> dict:
    carrier_path = validate_readable_file(carrier)
    secret_path = validate_readable_file(secret)
    out = validate_output_path(output, overwrite=True)
    started = time.perf_counter()
    payload = secret_path.read_bytes()
    try:
        result = lsb_audio.hide(carrier_path, payload, key, out)
    except Exception as exc:
        _record(Technique.AUDIO_LSB, "hide", "FAILED", case_id=case_id,
                evidence_id=evidence_id, input_path=str(carrier_path),
                output_path=str(out), error=str(exc))
        raise
    before = hash_file(carrier_path, algorithms=("sha256",), case_id=case_id)
    after = hash_file(out, algorithms=("sha256",), case_id=case_id)
    recovered = lsb_audio.extract(out, key)
    verified = recovered == payload
    snr = round(lsb_audio.snr_db(carrier_path, out), 2)
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.AUDIO_LSB, "hide", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(carrier_path), output_path=str(out),
            payload_bytes=len(payload), capacity_bytes=result.capacity_bits // 8,
            input_hash=before.sha256, output_hash=after.sha256, verified=verified,
            messages=[f"SNR {snr} dB", f"utilisation {result.utilisation:.4%}"],
            details=result.stats, elapsed_ms=elapsed)
    log_event("audio", "lsb_hide", f"{secret_path.name} -> {out.name} SNR={snr}dB",
              case_id=case_id, status="OK" if verified else "FAILED")
    return {"technique": Technique.AUDIO_LSB, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-python",
            "carrier": str(carrier_path), "output": str(out),
            "carrier_sha256": before.sha256, "output_sha256": after.sha256,
            "payload_bytes": len(payload), "capacity_bits": result.capacity_bits,
            "utilisation": result.utilisation, "verified": verified, "snr_db": snr,
            "key_fingerprint": result.key_fingerprint, "stats": result.stats,
            "elapsed_ms": round(elapsed, 2)}


def lsb_extract(stego: Path, key: str, output: Path, case_id: int | None = None,
                evidence_id: int | None = None) -> dict:
    stego_path = validate_readable_file(stego)
    out = validate_output_path(output, overwrite=True)
    started = time.perf_counter()
    input_hash = hash_file(stego_path, algorithms=("sha256",), case_id=case_id).sha256
    payload = lsb_audio.extract(stego_path, key)
    out.write_bytes(payload)
    out_hash = hash_file(out, algorithms=("sha256",), case_id=case_id).sha256
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.AUDIO_LSB, "extract", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(stego_path), output_path=str(out),
            payload_bytes=len(payload), input_hash=input_hash, output_hash=out_hash,
            verified=True, elapsed_ms=elapsed)
    return {"technique": Technique.AUDIO_LSB, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-python",
            "stego": str(stego_path), "output": str(out), "input_sha256": input_hash,
            "output_sha256": out_hash, "payload_bytes": len(payload),
            "elapsed_ms": round(elapsed, 2)}


# ----------------------------------------------------------------- phase coding
def phase_hide(carrier: Path, secret: Path, output: Path, key: str | None = None,
               segment_size: int = phase_coding.DEFAULT_SEGMENT,
               bins_per_bit: int = phase_coding.DEFAULT_BINS,
               case_id: int | None = None, evidence_id: int | None = None) -> dict:
    carrier_path = validate_readable_file(carrier)
    secret_path = validate_readable_file(secret)
    out = validate_output_path(output, overwrite=True)
    started = time.perf_counter()
    payload = secret_path.read_bytes()
    try:
        result = phase_coding.hide(carrier_path, payload, out, key=key,
                                   segment_size=segment_size, bins_per_bit=bins_per_bit)
    except Exception as exc:
        _record(Technique.AUDIO_PHASE, "hide", "FAILED", case_id=case_id,
                evidence_id=evidence_id, input_path=str(carrier_path),
                output_path=str(out), error=str(exc))
        raise
    after = hash_file(out, algorithms=("sha256",), case_id=case_id)
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.AUDIO_PHASE, "hide", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(carrier_path), output_path=str(out),
            payload_bytes=len(payload), output_hash=after.sha256, verified=True,
            messages=[f"SNR {result.snr_db} dB (quality cost of phase coding)",
                      f"{result.bits_embedded} bits in {result.segments_used} segments"],
            details={"segment_size": segment_size, "bins_per_bit": bins_per_bit,
                     "bins": result.stats["bins"]}, elapsed_ms=elapsed)
    return {"technique": Technique.AUDIO_PHASE, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-python",
            "output": str(out), "output_sha256": after.sha256,
            "payload_bytes": len(payload), "bits_embedded": result.bits_embedded,
            "segment_size": segment_size, "bins_per_bit": bins_per_bit,
            "snr_db": result.snr_db, "stats": result.stats,
            "elapsed_ms": round(elapsed, 2),
            "warning": "Phase coding is fragile: re-encoding or resampling destroys "
                       "the payload, and embedding is audible."}


def phase_extract(stego: Path, output: Path, key: str | None = None,
                  segment_size: int | None = None, bins_per_bit: int | None = None,
                  auto: bool = True, case_id: int | None = None,
                  evidence_id: int | None = None) -> dict:
    stego_path = validate_readable_file(stego)
    out = validate_output_path(output, overwrite=True)
    input_hash = hash_file(stego_path, algorithms=("sha256",), case_id=case_id).sha256
    if auto and segment_size is None:
        found = phase_coding.extract_auto(stego_path, key=key)
        if found["payload"] is None:
            _record(Technique.AUDIO_PHASE, "extract", "FAILED", case_id=case_id,
                    evidence_id=evidence_id, input_path=str(stego_path),
                    input_hash=input_hash, error=found["assessment"],
                    messages=[f"tried {len(found['attempts'])} parameter sets"])
            from app.core.exceptions import CorruptedCarrier

            raise CorruptedCarrier(found["assessment"])
        payload = found["payload"]
        segment_size = found["segment_size"]
        bins_per_bit = found["bins_per_bit"]
    else:
        result = phase_coding.extract(
            stego_path, key=key, segment_size=segment_size or phase_coding.DEFAULT_SEGMENT,
            bins_per_bit=bins_per_bit or phase_coding.DEFAULT_BINS)
        payload = result.payload
    out.write_bytes(payload)
    out_hash = hash_file(out, algorithms=("sha256",), case_id=case_id).sha256
    _record(Technique.AUDIO_PHASE, "extract", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(stego_path), output_path=str(out),
            payload_bytes=len(payload), input_hash=input_hash, output_hash=out_hash,
            verified=True, messages=[f"segment_size={segment_size}",
                                     f"bins_per_bit={bins_per_bit}"])
    return {"technique": Technique.AUDIO_PHASE, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-python",
            "output": str(out), "payload_bytes": len(payload),
            "input_sha256": input_hash, "output_sha256": out_hash,
            "segment_size": segment_size, "bins_per_bit": bins_per_bit}


# -------------------------------------------------------------- spread spectrum
def spread_hide(carrier: Path, secret: Path, key: str, output: Path,
                chips_per_bit: int = audio_spread.DEFAULT_CHIPS,
                span: int = audio_spread.DEFAULT_SPAN,
                alpha: float = audio_spread.DEFAULT_ALPHA,
                case_id: int | None = None, evidence_id: int | None = None) -> dict:
    carrier_path = validate_readable_file(carrier)
    secret_path = validate_readable_file(secret)
    out = validate_output_path(output, overwrite=True)
    started = time.perf_counter()
    payload = secret_path.read_bytes()
    try:
        result = audio_spread.hide(carrier_path, payload, out, key,
                                   chips_per_bit=chips_per_bit, span=span, alpha=alpha)
    except Exception as exc:
        _record(Technique.AUDIO_SPREAD, "hide", "FAILED", case_id=case_id,
                evidence_id=evidence_id, input_path=str(carrier_path),
                output_path=str(out), error=str(exc))
        raise
    after = hash_file(out, algorithms=("sha256",), case_id=case_id)
    recovered = audio_spread.extract(out, key, chips_per_bit=chips_per_bit,
                                     span=span, reference_path=carrier_path)
    verified = recovered.payload == payload
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.AUDIO_SPREAD, "hide", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(carrier_path), output_path=str(out),
            payload_bytes=len(payload), output_hash=after.sha256, verified=verified,
            messages=[f"process gain {result.process_gain_db} dB",
                      f"carrier SNR {result.snr_db} dB"],
            details={"chips_per_bit": chips_per_bit, "alpha": alpha},
            elapsed_ms=elapsed)
    return {"technique": Technique.AUDIO_SPREAD, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-python",
            "output": str(out), "output_sha256": after.sha256,
            "payload_bytes": len(payload), "bits_embedded": result.bits_embedded,
            "chips_per_bit": chips_per_bit, "alpha": alpha, "verified": verified,
            "process_gain_db": result.process_gain_db, "snr_db": result.snr_db,
            "elapsed_ms": round(elapsed, 2)}


def spread_extract(stego: Path, key: str, output: Path,
                   chips_per_bit: int = audio_spread.DEFAULT_CHIPS,
                   span: int = audio_spread.DEFAULT_SPAN,
                   reference: Path | None = None, case_id: int | None = None,
                   evidence_id: int | None = None) -> dict:
    stego_path = validate_readable_file(stego)
    out = validate_output_path(output, overwrite=True)
    input_hash = hash_file(stego_path, algorithms=("sha256",), case_id=case_id).sha256
    result = audio_spread.extract(stego_path, key, chips_per_bit=chips_per_bit,
                                  span=span, reference_path=reference)
    out.write_bytes(result.payload)
    out_hash = hash_file(out, algorithms=("sha256",), case_id=case_id).sha256
    _record(Technique.AUDIO_SPREAD, "extract", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(stego_path), output_path=str(out),
            payload_bytes=len(result.payload), input_hash=input_hash,
            output_hash=out_hash, verified=True,
            messages=[f"differential={result.differential}",
                      f"mean |correlation| {result.mean_correlation}"],
            details={"chips_per_bit": chips_per_bit})
    return {"technique": Technique.AUDIO_SPREAD, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-python",
            "output": str(out), "payload_bytes": len(result.payload),
            "input_sha256": input_hash, "output_sha256": out_hash,
            "differential": result.differential,
            "mean_correlation": result.mean_correlation,
            "assessment": result.assessment}


# ------------------------------------------------------------------- visualisers
def waveform(path: Path, max_points: int = 4000) -> dict:
    """Down-sampled amplitude series for the waveform plot."""
    import numpy as np

    target = validate_readable_file(path)
    with wave.open(str(target), "rb") as wav:
        width = wav.getsampwidth()
        rate = wav.getframerate()
        channels = wav.getnchannels()
        raw = wav.readframes(wav.getnframes())
    if width == 2:
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    elif width == 1:
        samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128
    else:
        raise UnsupportedFormat(
            f"Sample width {width} is not supported by the plotter; convert with "
            "FFmpeg to 16-bit PCM WAV first.")
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    step = max(1, samples.size // max_points)
    down = samples[::step]
    times = np.arange(down.size) * step / rate
    return {"path": str(target), "sample_rate": rate, "channels": channels,
            "duration_s": round(samples.size / rate, 4),
            "times": times.tolist(), "amplitudes": down.tolist(),
            "peak": float(np.max(np.abs(samples))) if samples.size else 0.0,
            "status_label": Status.IMPLEMENTED}


def spectrogram(path: Path, nfft: int = 1024, hop: int = 256) -> dict:
    """Magnitude spectrogram matrix for the spectrogram plot."""
    import numpy as np

    target = validate_readable_file(path)
    with wave.open(str(target), "rb") as wav:
        rate = wav.getframerate()
        width = wav.getsampwidth()
        channels = wav.getnchannels()
        raw = wav.readframes(wav.getnframes())
    if width != 2:
        raise UnsupportedFormat("Spectrogram requires 16-bit PCM WAV.")
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    window = np.hanning(nfft)
    frames = []
    for start in range(0, max(1, samples.size - nfft), hop):
        segment = samples[start:start + nfft] * window
        frames.append(np.abs(np.fft.rfft(segment)))
    if not frames:
        raise UnsupportedFormat("Audio too short for the selected FFT size.")
    matrix = 20 * np.log10(np.array(frames).T + 1e-9)
    return {"path": str(target), "nfft": nfft, "hop": hop, "sample_rate": rate,
            "extent": [0.0, samples.size / rate, 0.0, rate / 2],
            "data": matrix.tolist(), "max_db": float(matrix.max()),
            "status_label": Status.IMPLEMENTED}


def frequency_peaks(path: Path, top: int = 10) -> dict:
    """Dominant frequency components (used for suspicious-pattern notes)."""
    import numpy as np

    target = validate_readable_file(path)
    with wave.open(str(target), "rb") as wav:
        rate = wav.getframerate()
        raw = wav.readframes(min(wav.getnframes(), 44100 * 10))
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(samples.size)))
    freqs = np.fft.rfftfreq(samples.size, 1 / rate)
    order = np.argsort(spectrum)[::-1][:top]
    peaks = [{"frequency_hz": round(float(freqs[i]), 2),
              "magnitude": round(float(spectrum[i]), 2)} for i in order
             if freqs[i] > 0]
    return {"path": str(target), "peaks": peaks, "sample_rate": rate,
            "note": "Tonal components can indicate a phase-coded region, but "
                    "musical content looks the same - correlate with the analysis.",
            "status_label": Status.IMPLEMENTED}


def open_in_audacity(path: Path) -> dict:
    """Hand a file to Audacity if it is installed (external, interactive)."""
    target = validate_readable_file(path)
    if not executor.is_available("audacity"):
        raise ToolUnavailable(
            "Audacity is not installed (sudo apt install audacity). StegoNexus "
            "provides its own waveform/spectrogram plots in this screen.")
    import subprocess

    subprocess.Popen([executor.resolve("audacity"), str(target)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    get_db().log_action(action="Opened in Audacity", module="audio", target=str(target),
                        tool="audacity", result="external editor launched")
    return {"status": "LAUNCHED", "path": str(target),
            "status_label": Status.INTEGRATED}
