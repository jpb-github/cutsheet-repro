"""Main window of the Cutsheet Generator app: tabs, status bar with the cache size and a clear action, and a log dock.

A thin layer over the core: it gets a JobService (and through it the Cache) and knows nothing about parts or forms; the
tabs will emit generate_requested (the Drawer Blocks tab is empty for now). Worker threads write to the log through the log_requested signal.
"""
import time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QDockWidget, QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QTabWidget, QToolButton, QWidget)

from app.drawer_blocks_tab import DrawerBlocksTab
from app.about import APP_NAME, show_about
from app.job_controller import JobController
from app.theme import STYLESHEET, app_icon
from app.wait_cursor import WaitCursor
from app.save_flow import choose_destination, confirm_overwrite, report_save_error, run_save
from app.settings import last_dir, remember_dir
from core.cache import CacheError
from core.catalogue import Part
from core.jobs import JobResult, JobService

MAX_LOG_LINES = 5000


def format_size(n: int) -> str:
    if n < 1024:
        return "%d B" % n
    size = float(n)
    for unit in ("KB", "MB", "GB"):
        size /= 1024
        if size < 1024 or unit == "GB":
            return "%.1f %s" % (size, unit)


def _ask_clear(parent: QWidget, size_text: str) -> bool:
    answer = QMessageBox.question(parent, "Clear cache", "Delete all generated models (%s) from the cache?" % size_text,
                                  QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    return answer == QMessageBox.Yes


def _show_failure(parent: QWidget, error: str, details: str) -> None:
    box = QMessageBox(QMessageBox.Critical, "Generation failed", error, QMessageBox.Ok, parent)
    box.setDetailedText(details)
    box.exec()


# module-level defaults: the constructor arguments of the same names shadow the imported functions inside __init__
_choose_destination, _confirm_overwrite, _report_save_error = choose_destination, confirm_overwrite, report_save_error


class MainWindow(QMainWindow):
    log_requested = Signal(str)
    result_ready = Signal(object, object)       # Part, JobResult: only for successful jobs

    def __init__(self, service: JobService, *, confirm_clear: Callable[[QWidget, str], bool] | None = None,
                 report_failure: Callable[[QWidget, str, str], None] | None = None,
                 choose_destination: Callable | None = None, confirm_overwrite: Callable | None = None,
                 report_save_error: Callable | None = None):
        super().__init__()
        self.service = service
        self._confirm_clear = confirm_clear or _ask_clear
        self._report_failure = report_failure or _show_failure
        self._choose = choose_destination or _choose_destination
        self._confirm_overwrite = confirm_overwrite or _confirm_overwrite
        self._report_save_error = report_save_error or _report_save_error
        self.last_part: Part | None = None
        self.last_result: JobResult | None = None
        self._busy = False
        self._wait_cursor = WaitCursor()
        self._job_start = 0.0
        self._job_label = ""
        self._pieces_done = 0
        self.setWindowTitle("Cutsheet Generator")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(STYLESHEET)
        self.setWindowIcon(app_icon())

        self.tabs = QTabWidget()
        brand = QLabel("Cutsheet Generator")
        brand.setObjectName("brand")
        self.tabs.setCornerWidget(brand, Qt.TopLeftCorner)
        self.setCentralWidget(self.tabs)
        self.drawer_blocks_tab = DrawerBlocksTab()
        self.add_tab(self.drawer_blocks_tab, "Drawer Blocks")

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(MAX_LOG_LINES)
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self.log_dock.setWidget(self.log_view)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.resizeDocks([self.log_dock], [120], Qt.Vertical)
        self.log_dock.hide()                      # collapsed by default; View > Log shows it
        self.log_requested.connect(self.append_log)

        self.clear_cache_action = QAction("Clear cache", self)
        self.clear_cache_action.triggered.connect(self.clear_cache)
        self.clear_log_action = QAction("Clear log", self)
        self.clear_log_action.triggered.connect(self.log_view.clear)
        self.menuBar().addMenu("&Cache").addAction(self.clear_cache_action)
        view = self.menuBar().addMenu("&View")
        view.addAction(self.log_dock.toggleViewAction())
        view.addAction(self.clear_log_action)
        self.about_action = QAction("&About %s" % APP_NAME, self)
        self.about_action.triggered.connect(self.show_about)
        self.menuBar().addMenu("&Help").addAction(self.about_action)

        self.cache_label = QLabel()
        button = QToolButton()
        button.setDefaultAction(self.clear_cache_action)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("danger")
        self.cancel_button.setVisible(False)
        self.save_button = QPushButton("Save again")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_last)
        self.statusBar().addPermanentWidget(self.cancel_button)
        self.statusBar().addPermanentWidget(self.save_button)
        self.statusBar().addPermanentWidget(self.cache_label)
        self.statusBar().addPermanentWidget(button)
        self.refresh_cache_info()

        self.controller = JobController(service, self)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self.drawer_blocks_tab.generate_requested.connect(self.start_job)
        self.cancel_button.clicked.connect(self.controller.cancel)
        self.controller.job_started.connect(self._on_job_started)
        self.controller.job_line.connect(self.append_log)
        self.controller.job_line.connect(self._count_pieces)
        self.controller.job_finished.connect(self._on_job_finished)
        self.result_ready.connect(self._on_result_ready)

    def show_about(self) -> None:
        show_about(self)

    def add_tab(self, widget: QWidget, title: str) -> int:
        return self.tabs.addTab(widget, title)

    def show_status(self, text: str, timeout_ms: int = 0) -> None:
        self.statusBar().showMessage(text, timeout_ms)

    def append_log(self, text: str) -> None:
        self.log_view.appendPlainText(text)

    def cache_summary(self) -> str:
        try:
            cache = self.service.cache
            n, size = len(cache.entries()), cache.size()
        except (OSError, CacheError) as e:
            return "Cache: unavailable (%s)" % e
        return "Cache: %s in %d %s" % (format_size(size), n, "entry" if n == 1 else "entries")

    def refresh_cache_info(self) -> None:
        self.cache_label.setText(self.cache_summary())

    def clear_cache(self) -> bool:
        try:
            size_text = format_size(self.service.cache.size())
        except (OSError, CacheError):
            size_text = "unknown size"
        if not self._confirm_clear(self, size_text):
            return False
        try:
            freed = self.service.cache.clear()
        except (OSError, CacheError) as e:
            message = "Cannot clear the cache: %s" % e
            self.show_status(message)
            self.append_log(message)
            self.refresh_cache_info()
            return False
        message = "Cache cleared (%s freed)" % format_size(freed)
        self.show_status(message)
        self.append_log(message)
        self.refresh_cache_info()
        return True

    # ---- jobs ----
    def start_job(self, part: Part, params) -> bool:
        if self.controller.is_running():
            return False
        self.append_log("Generating %s with %s" % (part.label, dict(params)))
        return self.controller.start(part, params)

    @property
    def last_save_dir(self) -> Path:
        """The folder every save dialog starts in: remembered between launches, My Documents the first time (app.settings)."""
        return last_dir()

    @last_save_dir.setter
    def last_save_dir(self, folder) -> None:
        remember_dir(Path(folder))

    def _set_busy(self, busy: bool) -> None:
        self.drawer_blocks_tab.set_busy(busy)
        self.cancel_button.setVisible(busy)
        self.clear_cache_action.setEnabled(not busy)
        self._busy = busy
        self._wait_cursor.set(busy)
        self._update_save_button()

    def _update_save_button(self) -> None:
        self.save_button.setEnabled(self.last_result is not None and not self._busy)
        if self.last_part is not None:
            self.save_button.setToolTip("Save %s again" % self.last_part.label)

    def save_last(self) -> list[Path] | None:
        if self.last_result is None or self.last_result.entry is None:
            return None
        errors = []

        def report(parent, message):
            errors.append(message)
            self._report_save_error(parent, message)

        written = run_save(self.last_result.entry, self.last_save_dir, parent=self, choose=self._choose,
                           confirm=self._confirm_overwrite, report=report)
        if not written:
            self.append_log("Save failed: %s" % errors[0] if errors else "Save cancelled")
            return None
        first = written[0]
        main = self.last_result.entry.outputs[0]
        self.last_save_dir = first.parent.parent if main.is_dir() else first.parent
        self.show_status("Saved %d files in %s" % (len(written), first.parent) if main.is_dir() and len(written) > 1 else "Saved %s" % first)
        for path in written:
            self.append_log("Saved %s" % path)
        return written

    def _on_result_ready(self, part: Part, result: JobResult) -> None:
        self.save_last()

    def _on_job_started(self, label: str) -> None:
        self._job_label, self._job_start, self._pieces_done = label, time.monotonic(), 0
        self._set_busy(True)
        self._tick()
        self._timer.start()

    def _tick(self) -> None:
        text = "Generating %s ... %d s" % (self._job_label, int(time.monotonic() - self._job_start))
        if self._pieces_done:
            text += ", %d %s done" % (self._pieces_done, "piece" if self._pieces_done == 1 else "pieces")
        self.show_status(text)

    def _count_pieces(self, line: str) -> None:
        if line.startswith("wrote Piece"):
            self._pieces_done += 1

    def _on_job_finished(self, part: Part, result: JobResult) -> None:
        self._timer.stop()
        self._set_busy(False)
        self.refresh_cache_info()
        label = part.label
        if result.ok:
            text = "%s: from cache" % label if result.from_cache else "%s: done in %.1f s" % (label, result.elapsed)
            if result.warning:
                text += " (warning: %s)" % result.warning
                self.append_log("warning: %s" % result.warning)
            self.show_status(text)
            self.append_log(text)
            if self.last_result is not None:
                self.last_result.cleanup()
            self.last_part, self.last_result = part, result
            self._update_save_button()
            self.result_ready.emit(part, result)
        elif result.status == "cancelled":
            self.show_status("Cancelled")
            self.append_log("%s: cancelled" % label)
        else:
            details = result.tail(20)
            self.show_status("%s failed: %s" % (label, result.error))
            self.append_log("%s failed: %s" % (label, result.error))
            if details:
                self.append_log(details)
            self._report_failure(self, result.error, details)

    def closeEvent(self, event) -> None:
        if self.controller.is_running():
            self.controller.cancel()
            self.controller.wait(30)
        self._wait_cursor.set(False)
        super().closeEvent(event)
