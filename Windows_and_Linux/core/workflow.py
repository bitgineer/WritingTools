"""One workflow state for every surface.

The popup, progress pill, receipt, shell, and tray all read this object. A
response is applied only when its serial still matches the active run, so a
late answer from a cancelled or superseded request cannot paste.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from PySide6 import QtCore


class WorkflowState(str, Enum):
    IDLE = "idle"
    CAPTURING = "capturing"
    RUNNING = "running"
    REVIEWING = "reviewing"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowRun:
    option: str
    original: str = ""
    serial: int = 0
    revised: str = ""
    state: WorkflowState = WorkflowState.CAPTURING
    started_at: float = field(default_factory=time.monotonic)
    finished_at: float | None = None
    error: str = ""
    cancelled: bool = False

    @property
    def elapsed(self) -> float:
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return max(0.0, end - self.started_at)


class WorkflowController(QtCore.QObject):
    state_changed = QtCore.Signal(str, object)
    run_started = QtCore.Signal(object)
    run_finished = QtCore.Signal(object)
    run_failed = QtCore.Signal(object)
    run_cancelled = QtCore.Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = WorkflowState.IDLE
        self._active: WorkflowRun | None = None
        self._last: WorkflowRun | None = None
        self._serial = 0

    @property
    def state(self) -> WorkflowState:
        return self._state

    @property
    def active(self) -> WorkflowRun | None:
        return self._active

    @property
    def last(self) -> WorkflowRun | None:
        return self._last

    def _set(self, state: WorkflowState, run: WorkflowRun | None) -> None:
        self._state = state
        self.state_changed.emit(state.value, run)

    def begin(self, option: str, original: str = "") -> WorkflowRun:
        self._serial += 1
        run = WorkflowRun(serial=self._serial, option=option, original=original)
        self._active = run
        self._last = run
        self._set(WorkflowState.CAPTURING, run)
        self.run_started.emit(run)
        return run

    def set_original(self, serial: int, original: str) -> bool:
        if not self.is_current(serial):
            return False
        self._active.original = original
        self._set(WorkflowState.RUNNING, self._active)
        return True

    def finish(self, serial: int, revised: str) -> bool:
        if not self.is_current(serial):
            return False
        self._active.revised = revised
        self._active.finished_at = time.monotonic()
        self._active.state = WorkflowState.REVIEWING
        self._last = self._active
        self._active = None
        self._set(WorkflowState.REVIEWING, self._last)
        self.run_finished.emit(self._last)
        return True

    def fail(self, serial: int, error: str) -> bool:
        if not self.is_current(serial):
            return False
        self._active.error = error
        self._active.finished_at = time.monotonic()
        self._active.state = WorkflowState.FAILED
        self._last = self._active
        self._active = None
        self._set(WorkflowState.FAILED, self._last)
        self.run_failed.emit(self._last)
        return True

    def cancel(self) -> WorkflowRun | None:
        run = self._active
        if run is None:
            return None
        run.cancelled = True
        run.finished_at = time.monotonic()
        run.state = WorkflowState.CANCELLED
        self._last = run
        self._active = None
        self._set(WorkflowState.CANCELLED, run)
        self.run_cancelled.emit(run)
        return run

    def dismiss(self) -> None:
        if self._active is not None:
            return
        self._set(WorkflowState.IDLE, self._last)

    def reset(self) -> None:
        self._active = None
        self._last = None
        self._set(WorkflowState.IDLE, None)

    def is_current(self, serial: int) -> bool:
        return (
            self._active is not None
            and self._active.serial == serial
            and not self._active.cancelled
        )
