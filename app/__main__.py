"""Run the Cutsheet Generator app: python -m app [--check]

--check builds the window, processes pending events once, prints OK and exits 0 without entering the event loop (used by
the smoke tests; works without a display with QT_QPA_PLATFORM=offscreen).
"""
import argparse
import ctypes
import sys
from typing import Sequence

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.theme import APP_ID, app_icon
from core.cache import Cache
from core.jobs import JobService


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="build the window and exit")
    args = ap.parse_args(argv)
    try:        # own taskbar identity: the window is grouped under this icon, not under pythonw.exe
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except (AttributeError, OSError):
        pass
    qapp = QApplication.instance() or QApplication(sys.argv[:1])
    qapp.setWindowIcon(app_icon())
    window = MainWindow(JobService(Cache.default()))
    window.show()
    if args.check:
        qapp.processEvents()
        print("OK")
        window.close()
        return 0
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
