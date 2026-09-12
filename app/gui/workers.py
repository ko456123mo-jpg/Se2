"""Asynchronous execution so long operations never freeze the GUI.

A shared :class:`QThreadPool` runs :class:`Task` runnables.  Each task emits
``finished(result)`` or ``failed(error)`` and an optional ``progress(text)``.
"""
from __future__ import annotations

import traceback
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from app.core.exceptions import StegoNexusError
from app.core.logger import log_event


class _Signals(QObject):
    finished = Signal(object)
    failed = Signal(str, str)      # (type name, user message)
    progress = Signal(str)


class Task(QRunnable):
    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = _Signals()
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D102 - worker entry point
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except StegoNexusError as exc:
            self.signals.failed.emit(type(exc).__name__, exc.user_message())
            log_event("gui", "task_failed", str(exc), level=40, status="FAILED")
        except Exception as exc:  # noqa: BLE001 - keep full traceback in the log
            self.signals.failed.emit(type(exc).__name__,
                                     f"Unexpected error: {exc}")
            log_event("gui", "task_failed", f"{exc}\n{traceback.format_exc()}",
                      level=40, status="FAILED")


class Runner:
    """Thin facade around the global thread pool."""

    _pool: QThreadPool | None = None
    #: strong refs to in-flight tasks so Python never deletes a Task (which is
    #: ``setAutoDelete(True)``) before the worker thread executes it. without a live
    #: reference the C++ runnable is destroyed and emitting its signals raises
    #: ``RuntimeError: Signal source has been deleted``.
    _pending: set = set()

    @classmethod
    def pool(cls) -> QThreadPool:
        if cls._pool is None:
            cls._pool = QThreadPool.globalInstance()
            cls._pool.setMaxThreadCount(4)
        return cls._pool

    @staticmethod
    def _release(task: "Task") -> None:
        Runner._pending.discard(task)

    @staticmethod
    def run(fn: Callable, *args,
            on_done: Callable | None = None,
            on_error: Callable | None = None,
            on_progress: Callable | None = None,
            **kwargs) -> Task:
        # ``on_done`` / ``on_error`` / ``on_progress`` are keyword-only: the view
        # layer calls ``runner.run(fn, on_done=..., on_error=..., *args)`` where the
        # trailing positional ``*args`` are the *service* arguments.  If the callbacks
        # were positional parameters, the first service argument would bind to
        # ``on_done`` a second time and raise
        # ``TypeError: run() got multiple values for argument 'on_done'``.
        task = Task(fn, *args, **kwargs)
        # Retain the task until it finishes so the worker thread always sees a live
        # C++ runnable (see ``_pending`` above).
        Runner._pending.add(task)
        task.signals.finished.connect(lambda *_: Runner._release(task))
        task.signals.failed.connect(lambda *_: Runner._release(task))
        if on_done:
            task.signals.finished.connect(on_done)
        if on_error:
            task.signals.failed.connect(on_error)
        if on_progress:
            task.signals.progress.connect(on_progress)
        Runner.pool().start(task)
        return task
