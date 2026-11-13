import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from core.cache import Cache
from core.jobs import JobService


def test_window_has_the_drawer_blocks_tab_only_and_it_is_empty(tmp_path):
    QApplication.instance() or QApplication([])
    window = MainWindow(JobService(Cache(tmp_path / "cache")))
    try:
        assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == ["Drawer Blocks"]
        assert window.windowTitle() == "Cutsheet Generator"
        assert window.save_button.isEnabled() is False
        assert window.cache_label.text().startswith("Cache: ")
    finally:
        window.close()
