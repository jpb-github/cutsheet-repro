"""Cutsheet and Refine in the window: background search, save, open. Injected chooser and opener; iterations, no clock."""
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from dataclasses import replace  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.main_window import MainWindow  # noqa: E402
from core.cache import Cache  # noqa: E402
from core.cutting import Item, Sheet, Solution, Variant, pack, score  # noqa: E402
from core.jobs import JobService  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class Env:
    def __init__(self, tmp_path, qapp, answers):
        self.qapp, self.tmp = qapp, tmp_path
        self.answers = list(answers)       # what the chooser returns, one per call (a Path or None)
        self.asked, self.opened, self.errors = [], [], []
        self.window = MainWindow(JobService(Cache(tmp_path / "cache")),
                                 choose_cutsheet=self._choose, open_pdf=self.opened.append,
                                 report_save_error=lambda parent, m: self.errors.append(m))
        self.window.cutsheet_flow.iterations = 20
        self.window.cutsheet_flow.workers = 1
        self.tab = self.window.drawer_blocks_tab

    def _choose(self, parent, start):
        self.asked.append(start)
        return self.answers.pop(0) if self.answers else None

    def wait(self):
        end = time.monotonic() + 60
        while self.window.cutsheet_flow.is_running() and time.monotonic() < end:
            self.qapp.processEvents()
            time.sleep(0.01)
        self.qapp.processEvents()
        assert not self.window.cutsheet_flow.is_running(), "search did not finish"

    def cutsheet(self):
        self.tab.cutsheet_button.click()
        self.wait()

    def refine(self):
        self.tab.refine_button.click()
        self.wait()

    def close(self):
        self.window.close()


@pytest.fixture
def env(tmp_path, qapp):
    made = []

    def make(answers):
        e = Env(tmp_path, qapp, answers)
        made.append(e)
        return e
    yield make
    for e in made:
        e.close()


def test_cutsheet_writes_the_pdf_and_opens_it_once(env, tmp_path):
    e = env([tmp_path / "sheet.pdf"])
    assert e.tab.cutsheet_button.isEnabled() and not e.tab.refine_button.isEnabled()
    e.cutsheet()
    assert (tmp_path / "sheet.pdf").read_bytes().startswith(b"%PDF")
    assert e.opened == [tmp_path / "sheet.pdf"]
    assert e.asked[0].name == "Drawer Blocks - 2 drawers 760x350x540 cutsheet.pdf"
    assert "2 sheets" in e.window.statusBar().currentMessage() and "waste" in e.window.statusBar().currentMessage()
    assert e.tab.refine_button.isEnabled() and e.tab.cutsheet_button.isEnabled()


def test_chooser_returning_none_writes_nothing(env, tmp_path):
    e = env([None])
    e.cutsheet()
    assert e.opened == [] and list(tmp_path.glob("*.pdf")) == []
    assert "cancelled" in e.window.statusBar().currentMessage().lower()


def test_refine_keeps_or_improves_and_rewrites_only_when_better(env, tmp_path):
    e = env([tmp_path / "sheet.pdf"])
    e.cutsheet()
    first = e.window._cutsheet.score
    before = (tmp_path / "sheet.pdf").read_bytes()
    e.window.cutsheet_flow.iterations = 1                    # nothing better can come from one candidate
    e.refine()
    assert e.window._cutsheet.score == first
    assert (tmp_path / "sheet.pdf").read_bytes() == before and len(e.opened) == 1
    assert "no better" in e.window.statusBar().currentMessage().lower()
    # a deliberately weak first result: refine finds better and rewrites the same path
    state = e.window._cutsheet
    weak = {}
    for material, sol in state.solutions.items():
        items = [Item(p.label, p.h if p.rotated else p.w, p.w if p.rotated else p.h) for l in sol.layouts for p in l.placed]
        layouts = pack(items, Sheet(2400, 1200), 5, Variant("worst_area", "max_area", "shuffle", 5))
        weak[material] = Solution(tuple(layouts), score(layouts))
    weak_score = tuple(weak[m].score for m in sorted(weak))
    e.window._cutsheet = replace(state, solutions=weak, score=weak_score)
    e.window.cutsheet_flow.iterations = 60
    e.refine()
    assert e.window._cutsheet.score <= weak_score
    assert len(e.opened) == (2 if e.window._cutsheet.score < weak_score else 1)



def test_changing_the_form_disables_refine(env, tmp_path):
    e = env([tmp_path / "sheet.pdf"])
    e.cutsheet()
    assert e.tab.refine_button.isEnabled()
    e.tab.form.widget("drawers").setText("3")
    assert not e.tab.refine_button.isEnabled()


def test_cancel_still_gives_a_pdf_from_the_first_result(env, tmp_path):
    e = env([tmp_path / "sheet.pdf"])
    e.window.cutsheet_flow.iterations = 10 ** 9
    e.tab.cutsheet_button.click()
    e.window.cutsheet_flow.cancel()
    e.wait()
    assert (tmp_path / "sheet.pdf").read_bytes().startswith(b"%PDF")


def test_busy_disables_both_buttons(env, tmp_path):
    e = env([tmp_path / "sheet.pdf"])
    e.cutsheet()
    e.tab.set_busy(True)
    assert not e.tab.cutsheet_button.isEnabled() and not e.tab.refine_button.isEnabled()
    e.tab.set_busy(False)
    assert e.tab.cutsheet_button.isEnabled() and e.tab.refine_button.isEnabled()


def test_locked_file_reports_and_offers_another_name(env, tmp_path):
    (tmp_path / "locked.pdf").mkdir()                       # a folder in the way: the rename fails like a locked file
    e = env([tmp_path / "locked.pdf", tmp_path / "other.pdf"])
    e.cutsheet()
    assert len(e.errors) == 1 and "locked.pdf" in e.errors[0]
    assert (tmp_path / "other.pdf").read_bytes().startswith(b"%PDF")
    assert e.opened == [tmp_path / "other.pdf"]
    assert list(tmp_path.glob("*.part")) == []
