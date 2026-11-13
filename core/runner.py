"""Generator runner: runs one bundled script in a separate process and enforces the success contract.

Blocking by design: call it from a worker thread. CancelToken.cancel() may be called from any thread.
Standard library only (plus core.catalogue for the Invocation type).
"""
import os
import shutil
import signal
import subprocess
import sys
import threading
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Literal, Mapping

from core.catalogue import Invocation, Part

GENERATORS_DIR = Path(__file__).resolve().parent.parent / "generators"

# Harmless complaints OCCT's font parser prints at the start of a generator run on some machines (a damaged system font).
# They are kept in the run's log (error tails stay complete) but not streamed to the live log, where they read like errors.
NOISE_MARKERS = ("'name' table stringOffset incorrect", "too much 'OS/2' table data")


def is_noise(line: str) -> bool:
    return any(marker in line for marker in NOISE_MARKERS)


class CancelToken:
    def __init__(self):
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


@dataclass(frozen=True)
class RunResult:
    ok: bool
    status: Literal["ok", "failed", "cancelled", "timeout"]
    returncode: int | None
    outputs: tuple[Path, ...]
    log: str
    elapsed: float
    error: str
    work_dir: Path | None = None

    def tail(self, n: int = 20) -> str:
        return "\n".join([l for l in self.log.splitlines() if l.strip()][-n:])

    def cleanup(self) -> None:
        if self.work_dir is not None:
            shutil.rmtree(self.work_dir, ignore_errors=True)


def child_env(work_dir: Path, extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """The app's environment, sandboxed so only the bundle is found: an empty home folder (no installed skills); `extra` adds
    variables for the generator (the folder of the tile cache)."""
    home = Path(work_dir) / ".home"
    home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.pop("CUTSHEET_SKILLS", None)
    env.update(USERPROFILE=str(home), HOME=str(home), PYTHONUNBUFFERED="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    env.update(extra or {})
    return env


def kill_tree(proc: subprocess.Popen) -> None:
    """Kill the process and everything it started; silent when it is already gone."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def check_outputs(inv: Invocation, work_dir: Path, log: str) -> str:
    """The error text when a run that exited 0 did not deliver, or "" when the outputs are good."""
    lines = [l for l in log.splitlines() if l.strip()]
    if lines and lines[-1].strip().startswith(("CHECK FAILED", "FAILED")):
        return "the generator reported a failed check: %s" % lines[-1].strip()
    for name in inv.outputs:
        p = Path(work_dir) / name
        if p.is_dir():
            if not any(q.suffix.lower() == ".step" for q in p.rglob("*")):
                return "the generator folder %s has no STEP file" % name
        elif not p.exists():
            return "the generator did not produce %s" % name
        elif p.stat().st_size == 0:
            return "the generator produced an empty %s" % name
    return ""


def run_invocation(inv: Invocation, generators_dir: Path, work_dir: Path, *, python: str | None = None,
                   cancel: CancelToken | None = None, timeout: float | None = None,
                   on_line: Callable[[str], None] | None = None, env_extra: Mapping[str, str] | None = None) -> RunResult:
    """Run the script of inv in work_dir (which must exist). Never raises for generator problems."""
    start = time.monotonic()
    work_dir = Path(work_dir)
    script = Path(generators_dir) / inv.script

    def result(status, error, returncode=None, log="", outputs=()):
        return RunResult(status == "ok", status, returncode, tuple(outputs), log, time.monotonic() - start, error)

    if not script.is_file():
        return result("failed", "generator script not found: %s" % script)
    if cancel and cancel.cancelled:
        return result("cancelled", "cancelled by the user")
    try:
        proc = subprocess.Popen([python or sys.executable, str(script), *inv.args], cwd=str(work_dir), env=child_env(work_dir, env_extra),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                start_new_session=os.name != "nt")
    except OSError as e:
        return result("failed", "could not start the generator: %s" % e)
    chunks: list[str] = []

    def read():
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace")
            chunks.append(line)
            text = line.rstrip("\r\n")
            if on_line and not is_noise(text):
                on_line(text)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    deadline = None if timeout is None else start + timeout
    stopped = None
    while True:
        try:
            proc.wait(timeout=0.1)
            break
        except subprocess.TimeoutExpired:
            pass
        if cancel and cancel.cancelled:
            stopped = ("cancelled", "cancelled by the user")
        elif deadline is not None and time.monotonic() > deadline:
            stopped = ("timeout", "the generator did not finish within %g s" % timeout)
        if stopped:
            kill_tree(proc)
            proc.wait()
            break
    reader.join(5)
    log = "".join(chunks)
    if stopped:
        return result(stopped[0], stopped[1], proc.returncode, log)
    if proc.returncode != 0:
        return result("failed", "the generator exited with code %d" % proc.returncode, proc.returncode, log)
    error = check_outputs(inv, work_dir, log)
    if error:
        return result("failed", error, 0, log)
    return result("ok", "", 0, log, [work_dir / n for n in inv.outputs])


def run_part(part: Part, params: Mapping[str, object], generators_dir: Path, *, work_dir: Path | None = None,
             python: str | None = None, cancel: CancelToken | None = None, timeout: float | None = None,
             on_line: Callable[[str], None] | None = None, env_extra: Mapping[str, str] | None = None) -> RunResult:
    """Run a catalogue part with normalised params. Without work_dir a temp folder is made: it is left to the caller on
    success (RunResult.cleanup() after the outputs are moved) and removed here when the run is not ok. A given work_dir
    is never removed. A fixed part (no script) raises ValueError."""
    own = work_dir is None
    folder = Path(tempfile.mkdtemp(prefix="cutsheet_")) if own else Path(work_dir)
    try:
        inv = part.invocation(params, folder)
        result = run_invocation(inv, generators_dir, folder, python=python, cancel=cancel, timeout=timeout, on_line=on_line,
                                env_extra=env_extra)
    except BaseException:
        if own:
            shutil.rmtree(folder, ignore_errors=True)
        raise
    if own and not result.ok:
        shutil.rmtree(folder, ignore_errors=True)
        return result
    return replace(result, work_dir=folder) if own else result
