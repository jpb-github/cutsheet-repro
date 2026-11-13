"""Setup logic of the Cutsheet Generator launcher: choose a Python, build and check the private virtual environment.

Standard library only (it runs with the system Python before any library is installed) and importable on any OS.
The environment is built in place and a marker file (cutsheet_env.json) is written last, so an unfinished or failed build is
never trusted: a folder without a valid marker counts as broken and is rebuilt. Two launches at once share one build
through a lock file.
"""
import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Literal

MINIMUM = (3, 11)
MAXIMUM = (3, 14)       # newest Python tested with PySide6; raise when a newer one is checked
MARKER = "cutsheet_env.json"
LOCK_STALE_SECONDS = 600     # a lock that was not refreshed for this long belongs to a dead launcher
LOCK_WAIT_SECONDS = 1800
PIP_TAIL_LINES = 15


class SetupError(Exception):
    """The message is meant for the person using the app."""


def supported(version: tuple[int, int]) -> bool:
    return MINIMUM <= tuple(version)[:2] <= MAXIMUM


def _range_text() -> str:
    return "%d.%d to %d.%d" % (MINIMUM + MAXIMUM)


def _registry_reader() -> list[tuple[tuple[int, int], str]]:
    """(version, install path) of every PythonCore entry in HKCU and HKLM (64 bit view)."""
    try:
        import winreg
    except ImportError:
        return []
    found = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY,):      # 64 bit only: PySide6 has no 32 bit wheels
            try:
                core = winreg.OpenKey(hive, r"Software\Python\PythonCore", 0, winreg.KEY_READ | view)
            except OSError:
                continue
            with core:
                i = 0
                while True:
                    try:
                        name = winreg.EnumKey(core, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        major, minor = name.split("-")[0].split(".")[:2]
                        with winreg.OpenKey(core, name + r"\InstallPath", 0, winreg.KEY_READ | view) as k:
                            path = winreg.QueryValue(k, None)
                        found.append(((int(major), int(minor)), path))
                    except (OSError, ValueError):
                        continue
    return found


def find_pythons(registry: Callable[[], Iterable] | None = None) -> list[tuple[tuple[int, int], Path]]:
    """(version, pythonw.exe) of every installed Python with an existing pythonw.exe, newest first."""
    seen, out = set(), []
    for version, path in (registry or _registry_reader)():
        exe = Path(path) / "pythonw.exe"
        if exe.is_file() and (tuple(version), exe) not in seen:
            seen.add((tuple(version), exe))
            out.append((tuple(version), exe))
    return sorted(out, key=lambda item: item[0], reverse=True)


def pick_python(found: Iterable[tuple[tuple[int, int], Path]]) -> tuple[tuple[int, int], Path]:
    """The newest supported (version, pythonw.exe); SetupError naming what was found when there is none."""
    found = list(found)
    good = [item for item in found if supported(item[0])]
    if good:
        return max(good, key=lambda item: item[0])
    names = ", ".join(sorted({"%d.%d" % tuple(v) for v, _ in found})) or "none"
    raise SetupError("No supported Python found (found: %s). Cutsheet Generator needs Python %s: install it from python.org "
                     "and start the app again." % (names, _range_text()))


def requirements_hash(requirements: Path) -> str:
    text = Path(requirements).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(text).hexdigest()


def _venv_python(venv_dir: Path, name: str = "python.exe") -> Path:
    return Path(venv_dir) / "Scripts" / name


def env_status(venv_dir: Path, requirements: Path) -> Literal["ok", "missing", "outdated", "broken"]:
    venv_dir = Path(venv_dir)
    if not venv_dir.exists():
        return "missing"
    try:
        marker = json.loads((venv_dir / MARKER).read_text(encoding="utf-8"))
        base, wanted = Path(marker["base_python"]), marker["requirements"]
    except (OSError, ValueError, KeyError, TypeError):
        return "broken"
    if not base.is_file() or not _venv_python(venv_dir).is_file() or not _venv_python(venv_dir, "pythonw.exe").is_file():
        return "broken"
    return "ok" if wanted == requirements_hash(requirements) else "outdated"


def run_streaming(cmd: list, on_line: Callable[[str], None]) -> int:
    """Run cmd without a console window, passing every output line to on_line; returns the exit code."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", creationflags=flags)
    for line in proc.stdout:
        on_line(line.rstrip("\r\n"))
    return proc.wait()


class _Lock:
    """A lock file shared by the launchers of one user. Progress lines refresh it (touch), so only a launcher that died
    leaves a lock that goes stale."""

    def __init__(self, path: Path, on_wait: Callable[[str], None] | None = None, poll: float = 0.05):
        self.path, self.on_wait, self.poll = Path(path), on_wait, poll

    def touch(self) -> None:
        try:
            os.utime(self.path, None)
        except OSError:
            pass

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        announced = False
        while True:
            try:
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                try:
                    seen = self.path.stat().st_mtime
                    if time.time() - seen > LOCK_STALE_SECONDS:
                        if self.path.stat().st_mtime == seen:       # not refreshed or replaced meanwhile
                            self.path.unlink()
                        continue
                except OSError:
                    continue
                if not announced and self.on_wait:
                    announced = True
                    self.on_wait("Another Cutsheet Generator setup is running; waiting for it to finish ...")
                if time.monotonic() > deadline:
                    raise SetupError("Another Cutsheet Generator setup is still running. Close it and start the app again.")
                time.sleep(self.poll)

    def __exit__(self, *exc):
        try:
            self.path.unlink()
        except OSError:
            pass


def build_env(base_python: Path, venv_dir: Path, requirements: Path, on_progress: Callable[[str], None],
              run: Callable = run_streaming, version: tuple[int, int] | None = None, lock_path: Path | None = None) -> None:
    """Create venv_dir from base_python (a pythonw.exe) and install requirements; the marker is written last.

    Waits for a build already running in another process and then re-checks instead of building twice. On failure
    nothing is left behind and a SetupError carries the last pip lines.
    """
    base_python, venv_dir, requirements = Path(base_python), Path(venv_dir), Path(requirements)
    lock = _Lock(lock_path or venv_dir.parent / "setup.lock", on_progress)
    with lock:
        if env_status(venv_dir, requirements) == "ok":
            return
        if venv_dir.exists():
            shutil.rmtree(venv_dir)
        tail: list[str] = []

        def on_line(line: str) -> None:
            lock.touch()
            tail.append(line)
            del tail[:-PIP_TAIL_LINES]
            on_progress(line)

        try:
            on_progress("Creating the environment ...")
            if run([base_python.with_name("python.exe"), "-m", "venv", venv_dir], on_line) != 0:
                raise SetupError("Could not create the Python environment.\n" + "\n".join(tail))
            on_progress("Downloading the libraries (this takes a few minutes the first time) ...")
            cmd = [_venv_python(venv_dir), "-m", "pip", "install", "--disable-pip-version-check", "-r", requirements]
            if run(cmd, on_line) != 0:
                raise SetupError("Installing the libraries failed. Check the internet connection and start the app "
                                 "again.\n" + "\n".join(tail))
            marker = {"requirements": requirements_hash(requirements), "base_python": str(base_python),
                      "python_version": "%d.%d" % tuple(version) if version else "",
                      "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            (venv_dir / MARKER).write_text(json.dumps(marker, indent=1), encoding="utf-8")
        except BaseException:
            shutil.rmtree(venv_dir, ignore_errors=True)
            raise
