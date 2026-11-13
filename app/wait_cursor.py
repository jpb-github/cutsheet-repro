"""The wait cursor over the whole app while a generation runs (the generator scripts take seconds to minutes)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


class WaitCursor:
    """set(True) puts the wait cursor on every window, set(False) restores the previous one; calls are balanced, so setting
    the same state twice (a job that starts while an export runs) never stacks or leaks an override."""

    def __init__(self):
        self.active = False

    def set(self, on: bool) -> None:
        if on and not self.active:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.active = True
        elif not on and self.active:
            QApplication.restoreOverrideCursor()
            self.active = False
