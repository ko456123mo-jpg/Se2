"""ToolExecutor - the single, safe gateway to external binaries (project rule 59).

Hard rules implemented here:

* ``subprocess.run(argv_list)`` - **never** ``shell=True``.
* argv is fully validated: strings only, no ``None``, target paths must resolve.
* per-call timeout, output size cap, structured result object.
* every execution is recorded in ``tool_executions`` and the JSON log.
* missing tools return ``ToolResult(available=False)`` - they are never faked.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Sequence

from app.core.config import get_config
from app.core.constants import DEFAULT_TOOL_TIMEOUT, MAX_TOOL_STDOUT_BYTES, Status
from app.core.exceptions import ToolTimeout, ToolUnavailable, ValidationError
from app.core.logger import log_event
from app.core.models import ToolResult
from app.storage.database import get_db


class ToolExecutor:
    """Discovers and executes external forensic/steganography tools."""

    def __init__(self, timeout: int | None = None):
        self._timeout = timeout
        self._version_cache: dict[str, str] = {}

    # ------------------------------------------------------------- discovery
    def resolve(self, tool: str) -> str | None:
        """Return the absolute path of a tool, honouring user overrides."""
        cfg = get_config()
        override = getattr(cfg.tool_overrides, tool.replace("-", "_"), "")
        if override:
            p = Path(override).expanduser()
            if p.is_file() and os.access(p, os.X_OK):
                return str(p)
        found = shutil.which(tool)
        return found

    def is_available(self, tool: str) -> bool:
        return self.resolve(tool) is not None

    def require(self, tool: str) -> str:
        path = self.resolve(tool)
        if not path:
            raise ToolUnavailable(
                f"Required tool '{tool}' is not installed or not on PATH.",
                details={"tool": tool, "status": Status.UNAVAILABLE})
        return path

    @property
    def timeout(self) -> int:
        return self._timeout or get_config().tool_timeout or DEFAULT_TOOL_TIMEOUT

    # ------------------------------------------------------------- execution
    def run(self, tool: str, args: Sequence[str], *, timeout: int | None = None,
            cwd: str | Path | None = None, input_bytes: bytes | None = None,
            case_id: int | None = None, raise_on_error: bool = False,
            env: dict[str, str] | None = None) -> ToolResult:
        """Execute ``tool args`` safely and return a structured result."""
        argv = self._validated_argv(tool, args)
        started = time.perf_counter()
        result = ToolResult(tool=tool, argv=argv, available=False)

        binary = self.resolve(tool)
        if binary is None:
            result.error = f"Tool '{tool}' not found on PATH."
            self._record(result, case_id, (time.perf_counter() - started) * 1000)
            if raise_on_error:
                raise ToolUnavailable(result.error, details={"tool": tool})
            return result

        argv[0] = binary
        result.available = True
        run_env = dict(os.environ)
        if env:
            run_env.update({k: str(v) for k, v in env.items()})
        try:
            completed = subprocess.run(          # noqa: S603 - explicit argv, no shell
                argv,
                cwd=str(cwd) if cwd else None,
                input=input_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout or self.timeout,
                check=False,
                env=run_env,
            )
        except subprocess.TimeoutExpired as exc:
            result.timed_out = True
            result.error = f"{tool} exceeded {timeout or self.timeout}s timeout."
            result.stdout = self._decode(exc.stdout)
            result.stderr = self._decode(exc.stderr)
            elapsed = (time.perf_counter() - started) * 1000
            self._record(result, case_id, elapsed)
            if raise_on_error:
                raise ToolTimeout(result.error, details={"tool": tool}) from exc
            return result
        except OSError as exc:
            result.error = f"Could not execute {tool}: {exc}"
            elapsed = (time.perf_counter() - started) * 1000
            self._record(result, case_id, elapsed)
            if raise_on_error:
                raise ToolUnavailable(result.error, details={"tool": tool}) from exc
            return result

        result.returncode = completed.returncode or 0
        result.stdout, out_trunc = self._capped(self._decode(completed.stdout))
        result.stderr, err_trunc = self._capped(self._decode(completed.stderr))
        result.truncated = out_trunc or err_trunc
        elapsed = (time.perf_counter() - started) * 1000
        self._record(result, case_id, elapsed)

        if raise_on_error and not result.ok:
            from app.core.exceptions import ToolExecutionError

            raise ToolExecutionError(
                f"{tool} failed (exit {result.returncode}): "
                f"{result.stderr.strip()[:400] or 'no stderr'}",
                details={"tool": tool, "argv": argv})
        return result

    # ------------------------------------------------------------------ helpers
    def _validated_argv(self, tool: str, args: Sequence[str]) -> list[str]:
        if not tool or not isinstance(tool, str):
            raise ValidationError("Tool name must be a non-empty string.")
        argv = [tool]
        for arg in args:
            if arg is None:
                raise ValidationError(f"Null argument passed to {tool}.")
            if not isinstance(arg, (str, int, float, Path)):
                raise ValidationError(
                    f"Argument of type {type(arg).__name__} rejected for {tool}.")
            text = str(arg)
            if "\x00" in text:
                raise ValidationError(f"NUL byte rejected in argument to {tool}.")
            argv.append(text)
        return argv

    @staticmethod
    def _decode(data: bytes | str | None) -> str:
        if data is None:
            return ""
        if isinstance(data, str):
            return data
        return data.decode("utf-8", errors="replace")

    @staticmethod
    def _capped(text: str) -> tuple[str, bool]:
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= MAX_TOOL_STDOUT_BYTES:
            return text, False
        return encoded[:MAX_TOOL_STDOUT_BYTES].decode("utf-8", errors="replace"), True

    def _record(self, result: ToolResult, case_id: int | None, elapsed_ms: float) -> None:
        result.elapsed_ms = round(elapsed_ms, 2)
        try:
            get_db().record_tool_execution({
                "tool": result.tool,
                "argv": result.argv,
                "available": result.available,
                "returncode": result.returncode,
                "status": result.status,
                "stdout_len": len(result.stdout),
                "stderr_len": len(result.stderr),
                "stderr_head": result.stderr.strip(),
                "timed_out": result.timed_out,
                "elapsed_ms": result.elapsed_ms,
                "case_id": case_id,
            })
        except Exception:  # pragma: no cover - logging must never break analysis
            pass
        log_event("tool_executor", "tool_run", result.summary(),
                  tool=result.tool, status=result.status, case_id=case_id)

    # ---------------------------------------------------------------- versions
    def version(self, tool: str, args: Sequence[str] = ("--version",)) -> str:
        """Return a one-line version string, or '' when unavailable."""
        if tool in self._version_cache:
            return self._version_cache[tool]
        text = ""
        if self.is_available(tool):
            res = self.run(tool, args, timeout=20)
            lines = [ln.strip() for ln in (res.stdout or res.stderr).splitlines()]
            lines = [ln for ln in lines if ln]
            text = lines[0][:160] if lines else ""
        self._version_cache[tool] = text
        return text


executor = ToolExecutor()
