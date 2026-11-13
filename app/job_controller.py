"""Runs JobService.get on a worker thread and reports through Qt signals, so the GUI thread never blocks.

Only the signals cross threads: the controller lives in the GUI thread, the worker emits, and Qt queues the delivery.
One job at a time: start() refuses while one is running.
"""
import threading
from typing import Mapping

from PySide6.QtCore import QCoreApplication, QObject, Signal

from core.catalogue import Part
from core.jobs import JobResult, JobService
from core.runner import CancelToken


class JobController(QObject):
    job_started = Signal(str)             # the part label
    job_line = Signal(str)                # one line of generator output
    job_finished = Signal(object, object)  # Part, JobResult

    def __init__(self, service: JobService, parent: QObject | None = None):
        super().__init__(parent)
        self.service = service
        self._running = False
        self._thread: threading.Thread | None = None
        self._token: CancelToken | None = None
        self.job_finished.connect(self._on_finished)

    def _on_finished(self, *_args) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def start(self, part: Part, params: Mapping[str, object]) -> bool:
        if self._running:
            return False
        self._running = True
        self._token = token = CancelToken()

        def work():
            try:
                result = self.service.get(part, params, cancel=token, on_line=self.job_line.emit)
            except BaseException as e:           # a bug must not leave the UI "running" forever
                result = JobResult(False, "failed", None, False, None, error="internal error: %s" % e)
            self.job_finished.emit(part, result)

        self._thread = threading.Thread(target=work, daemon=True)
        self.job_started.emit(part.label)
        self._thread.start()
        return True

    def cancel(self) -> None:
        if self._token is not None:
            self._token.cancel()

    def wait(self, timeout: float) -> bool:
        """Join the worker (and deliver its finished signal); True when no job is running afterwards."""
        if self._thread is not None:
            self._thread.join(timeout)
            if self._thread.is_alive():
                return False
        QCoreApplication.processEvents()
        return not self._running
