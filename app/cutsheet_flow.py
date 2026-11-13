"""The background search of the cutsheet: runs core.cutsheet.plan_cutsheet in a thread so the window stays alive.

Signals: progress(str) with the best layout so far, finished(object) with a FlowResult, failed(str) with a readable message.
Cancel keeps the best layout found (at least the first run) and still finishes normally. The settings `seconds`, `iterations` and
`workers` are plain attributes (tests set `iterations`, so no clock is involved).
"""
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal

from core.cutting import CutError, Solution
from core.cutsheet import plan_cutsheet
from core.params import ParamError


@dataclass(frozen=True)
class FlowResult:
    params: dict
    solutions: dict            # material -> Solution
    refine: bool
    cancelled: bool


def total_score(solutions) -> tuple:
    """One comparable score for all the materials (each one is never worse after a refine)."""
    return tuple(solutions[m].score for m in sorted(solutions))


class _Worker(QThread):
    best = Signal(str)

    def __init__(self, flow, params, refine, start, seed):
        super().__init__(flow)
        self.flow, self.params, self.refine, self.start_from, self.seed = flow, params, refine, start, seed
        self.result = None
        self.error = ""

    def run(self):
        flow = self.flow
        latest = {}

        def progress(material, solution: Solution):
            latest[material] = solution
            self.best.emit(", ".join("%s: %d sheet%s" % (m, s.score[0], "" if s.score[0] == 1 else "s") for m, s in sorted(latest.items())))

        try:
            solutions = plan_cutsheet(self.params, seconds=flow.seconds, iterations=flow.iterations, workers=flow.workers,
                                      seed=self.seed, start=self.start_from, on_progress=progress, cancel=lambda: flow.cancelled)
            self.result = FlowResult(self.params, solutions, self.refine, flow.cancelled)
        except (ParamError, CutError) as e:
            self.error = str(e)
        except Exception as e:              # never let a thread die silently
            self.error = "The search failed: %s" % e


class CutsheetFlow(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.seconds = 15.0
        self.iterations = None
        self.workers = None
        self.cancelled = False
        self._worker: _Worker | None = None

    def is_running(self) -> bool:
        return self._worker is not None

    def start(self, params, *, refine: bool = False, start=None, seed: int = 0) -> bool:
        if self._worker is not None:
            return False
        self.cancelled = False
        worker = _Worker(self, dict(params), refine, start, seed)
        worker.best.connect(self.progress)
        worker.finished.connect(self._done)
        self._worker = worker
        worker.start()
        return True

    def cancel(self) -> None:
        self.cancelled = True

    def wait(self, seconds: float = 30) -> None:
        if self._worker is not None:
            self._worker.wait(int(seconds * 1000))

    def _done(self) -> None:
        worker, self._worker = self._worker, None
        if worker is None:
            return
        worker.wait()
        worker.deleteLater()
        if worker.result is not None:
            self.finished.emit(worker.result)
        else:
            self.failed.emit(worker.error or "The search failed.")
