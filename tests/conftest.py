"""Qt test session setup: one long-lived QApplication and a clean shutdown.

Several GUI test modules left parentless widgets (forms, tabs, windows) alive. At interpreter exit they were destroyed
in an arbitrary order and pytest died with a segmentation fault after all tests had passed. Fix: close and delete every
top-level widget, collect garbage and flush the deferred deletes in pytest_sessionfinish, while the QApplication still
exists. The instance is created here and kept in a module global so the per-module `qapp` fixtures (QApplication.instance()
or a new one) all find the same one.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:           # the GUI tests skip themselves without PySide6
    QApplication = None

_APP = QApplication.instance() or QApplication([]) if QApplication is not None else None


def pytest_sessionfinish(session, exitstatus):
    if _APP is None:
        return
    import gc
    from PySide6.QtCore import QCoreApplication, QEvent
    for w in _APP.topLevelWidgets():
        w.close()
        w.deleteLater()
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    _APP.processEvents()


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """No test reads or writes the real user settings: each one gets its own empty settings folder."""
    monkeypatch.setenv("CUTSHEET_SETTINGS_DIR", str(tmp_path / "cs-settings"))


@pytest.fixture(autouse=True)
def _collect_garbage_between_tests():
    """Windows that earlier tests left alive are destroyed here, between two tests, and not by a collection that happens to run inside
    the event loop of a later test (that aborted the interpreter: 'Fatal Python error: Aborted' in a pump(), depending on the number of
    objects a window creates)."""
    yield
    import gc
    gc.collect()
