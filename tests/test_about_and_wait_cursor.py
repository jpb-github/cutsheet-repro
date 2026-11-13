import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app import about
from app.main_window import MainWindow
from core.cache import Cache
from core.jobs import JobService


def test_the_version_comes_from_the_version_file(tmp_path):
    assert about.read_version() == (about.VERSION_FILE).read_text(encoding="utf-8").strip() != ""
    assert about.read_version(tmp_path / "missing") == "unknown"
    (tmp_path / "VERSION").write_text("9.8.7", encoding="utf-8")
    assert "Version 9.8.7" in about.about_text(about.read_version(tmp_path / "VERSION"))


def test_help_menu_shows_the_about_box_with_the_version(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    shown = []
    monkeypatch.setattr(QMessageBox, "about", staticmethod(lambda parent, title, text: shown.append((title, text))))
    window = MainWindow(JobService(Cache(tmp_path / "cache")))
    try:
        assert "Help" in [a.text().replace("&", "") for a in window.menuBar().actions()]
        window.about_action.trigger()
        assert shown and about.APP_NAME in shown[0][0]
        assert about.APP_NAME in shown[0][1] and "Version " + about.read_version() in shown[0][1] and about.DESCRIPTION in shown[0][1]
    finally:
        window.close()


def test_the_wait_cursor_follows_the_busy_state(tmp_path):
    QApplication.instance() or QApplication([])
    window = MainWindow(JobService(Cache(tmp_path / "cache")))
    try:
        assert QApplication.overrideCursor() is None
        window._set_busy(True)
        window._set_busy(True)                                        # balanced: one override however often it is set
        assert QApplication.overrideCursor().shape() == Qt.WaitCursor
        window._set_busy(False)
        assert QApplication.overrideCursor() is None
        window._set_busy(True)
    finally:
        window.close()                                                # closing restores the cursor
    assert QApplication.overrideCursor() is None
