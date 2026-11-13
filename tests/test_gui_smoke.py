"""End-to-end smoke test of the window with the real JobService and the bundled generator: generate, save, cache hit."""
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.main_window import MainWindow  # noqa: E402
from core.cache import Cache  # noqa: E402
from core.jobs import JobService  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_generate_save_then_cache_hit(tmp_path, qapp):
    targets = [tmp_path / "out" / "list.csv", tmp_path / "out" / "again.csv"]
    targets[0].parent.mkdir()
    failures, save_errors = [], []
    w = MainWindow(JobService(Cache(tmp_path / "cache")), report_failure=lambda *a: failures.append(a),
                   choose_destination=lambda parent, start, is_folder: targets.pop(0), confirm_overwrite=lambda parent, paths: True,
                   report_save_error=lambda parent, m: save_errors.append(m))
    first, second = tmp_path / "out" / "list.csv", tmp_path / "out" / "again.csv"
    try:
        w.show()
        tab = w.drawer_blocks_tab

        def run():
            tab.generate_button.click()
            end = time.monotonic() + 60
            while w.controller.is_running() and time.monotonic() < end:
                qapp.processEvents()
                time.sleep(0.02)
            qapp.processEvents()
            assert not w.controller.is_running(), "job did not finish"

        run()
        assert failures == [] and save_errors == []
        assert w.last_part.key == "drawer_blocks" and w.last_result.ok and not w.last_result.from_cache
        lines = first.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "Piece,Material,Thickness,Quantity,Length,Width" and "Drawer bottom,thin,6,2,694,500" in lines
        assert '"Pocket screw, box","32 mm, fine thread (18 mm sheet); 5 per joint x 4 joints",20' in lines and "Drawer pull,one per drawer,2" in lines
        assert "wrote Drawer Blocks - 2 drawers 760x350x540.csv" in w.log_view.toPlainText()
        run()                                                                         # the same request again: from the cache
        assert w.last_result.from_cache and second.read_text(encoding="utf-8") == first.read_text(encoding="utf-8")
    finally:
        w.controller.cancel()
        w.controller.wait(30)
        w.close()
