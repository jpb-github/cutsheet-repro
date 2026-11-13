"""Cutsheet Generator launcher: make sure the private environment is ready, then start the app.

Run by the Start menu shortcut with the system pythonw.exe (no console window):
  pythonw launch.pyw [--app-dir DIR] [--venv DIR]
First launch (or an outdated or broken environment): a progress window while the libraries are downloaded into the
environment (default %LOCALAPPDATA%\\CutsheetGenerator\\venv). Problems are shown in a message box and appended to %LOCALAPPDATA%\\CutsheetGenerator\\launcher.log.
Standard library only; tkinter is optional (a message box is the fallback).
"""
import argparse
import ctypes
import os
import queue
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

sys.dont_write_bytecode = True      # this runs from the install folder: leave no bytecode there (the uninstaller does not know it)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cutsheet_setup  # noqa: E402

TITLE = "Cutsheet Generator"


def local_appdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")


def log_path() -> Path:
    return local_appdata() / "CutsheetGenerator" / "launcher.log"


def message_box(title: str, text: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
    except (AttributeError, OSError):
        sys.stderr and sys.stderr.write("%s: %s\n" % (title, text))


class Ui:
    def progress(self, text: str) -> None:
        pass

    def error(self, title: str, text: str) -> None:
        message_box(title, text)

    def run(self, fn: Callable[[], object]) -> object:
        return fn()

    def close(self) -> None:
        pass


class BoxUi(Ui):
    """No progress window (tkinter missing): errors go to a message box, progress is not shown."""


class TkUi(Ui):
    def __init__(self):
        import tkinter
        self._tk = tkinter
        self.lines: "queue.Queue[str]" = queue.Queue()
        self.root = tkinter.Tk()
        self.root.title(TITLE + " setup")
        self.root.resizable(False, False)
        tkinter.Label(self.root, text="Setting up Cutsheet Generator (first launch only) ...", padx=16, pady=8).pack()
        self.label = tkinter.Label(self.root, text="", width=80, height=6, anchor="nw", justify="left", padx=16, pady=4)
        self.label.pack()
        self.recent: list[str] = []

    def progress(self, text: str) -> None:
        self.lines.put(text)

    def _poll(self, worker: threading.Thread) -> None:
        try:
            while True:
                self.recent.append(self.lines.get_nowait())
                del self.recent[:-6]
        except queue.Empty:
            pass
        self.label.config(text="\n".join(line[:100] for line in self.recent))
        if worker.is_alive():
            self.root.after(150, self._poll, worker)
        else:
            self.root.quit()

    def run(self, fn: Callable[[], object]) -> object:
        box: dict = {}
        def work():
            try:
                box["result"] = fn()
            except BaseException as e:      # handed back to the caller after the window closed
                box["error"] = e
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        self.root.after(100, self._poll, worker)
        self.root.mainloop()
        worker.join()
        if "error" in box:
            raise box["error"]
        return box.get("result")

    def close(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass


def make_ui(tk_available: bool | None = None) -> Ui:
    if tk_available is None:
        try:
            import tkinter  # noqa: F401
            tk_available = True
        except ImportError:
            tk_available = False
    if tk_available:
        try:
            return TkUi()
        except Exception:
            pass
    return BoxUi()


def _log(text: str) -> None:
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write("[%s]\n%s\n" % (datetime.now().isoformat(timespec="seconds"), text))
    except OSError:
        pass


def main(argv: Sequence[str] | None = None, *, ui: Ui | None = None, setup=cutsheet_setup, start=subprocess.Popen) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--app-dir", default=str(HERE.parent.parent))
    ap.add_argument("--venv", default=str(local_appdata() / "CutsheetGenerator" / "venv"))
    args = ap.parse_args(argv)
    app_dir, venv = Path(args.app_dir), Path(args.venv)
    requirements = app_dir / "requirements.txt"
    shown = ui

    def finish() -> None:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")      # keep the install folder free of untracked files
        start([str(venv / "Scripts" / "pythonw.exe"), "-m", "app"], cwd=str(app_dir), env=env)

    try:
        status = setup.env_status(venv, requirements)
        if status == "ok":
            finish()
            return 0
        shown = shown or make_ui()

        def work() -> None:
            if status in ("outdated", "broken"):
                shown.progress("Updating the Cutsheet Generator environment ...")
            version, base = setup.pick_python(setup.find_pythons())
            setup.build_env(base, venv, requirements, shown.progress, version=version)
            finish()

        shown.run(work)
        shown.close()
        return 0
    except setup.SetupError as e:
        _log(str(e))
        (shown or Ui()).close()
        (shown or Ui()).error(TITLE, str(e))
        return 1
    except Exception as e:
        _log(traceback.format_exc())
        (shown or Ui()).close()
        (shown or Ui()).error(TITLE, "Cutsheet Generator could not start: %s\n\nDetails are in %s" % (e, log_path()))
        return 1


if __name__ == "__main__":
    sys.exit(main())
