"""Job service: get a part (cache hit, or generate and cache) and save a cached model to a chosen place.

Blocking and thread-safe; the caller runs it on a worker thread. The service never asks the user anything: overwriting
needs overwrite=True, passed by the caller after the user confirmed. Standard library plus the core modules.
"""
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Mapping

from core.cache import Cache, CacheError, Entry
from core.catalogue import Part
from core.params import ParamError
from core.runner import GENERATORS_DIR, CancelToken, RunResult, run_part


class SaveError(Exception):
    pass


class SaveConflict(SaveError):
    def __init__(self, paths):
        self.paths = tuple(paths)
        more = len(self.paths) - 1
        super().__init__("would overwrite: %s%s" % (self.paths[0], " and %d more" % more if more else ""))


TMP_SUFFIX = ".cutsheet_tmp"


def default_save_name(entry: Entry) -> str:
    return entry.outputs[0].name


def save_targets(entry: Entry, dest: Path) -> list[tuple[Path, Path]]:
    """(source file, target file) pairs for saving entry at dest (a folder for a folder entry, else the main file)."""
    dest = Path(dest)
    main = entry.outputs[0]
    if not main.exists():
        raise SaveError("the cached model is no longer available, generate it again")
    if main.is_dir():
        return [(p, dest / p.relative_to(main)) for p in sorted(main.rglob("*")) if p.is_file()]
    pairs = [(main, dest)]
    for out in entry.outputs[1:]:
        if not out.exists():
            raise SaveError("the cached model is no longer available, generate it again")
        name = dest.stem + out.name[len(main.stem):] if out.name.startswith(main.stem) else out.name
        pairs.append((out, dest.parent / name))
    return pairs


def find_conflicts(entry: Entry, dest: Path) -> list[Path]:
    return [t for _, t in save_targets(entry, dest) if t.exists()]


def _inside(path: Path, folder: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(os.path.abspath(folder))
        return True
    except ValueError:
        return False


def save(entry: Entry, dest: Path, *, overwrite: bool = False) -> list[Path]:
    """Copy entry to dest. Raises SaveConflict (nothing written) when files would be replaced and overwrite is False."""
    dest = Path(dest)
    pairs = save_targets(entry, dest)
    is_folder = entry.outputs[0].is_dir()
    if is_folder and dest.is_file():
        raise SaveError("the destination is a file, not a folder: %s" % dest)
    if not is_folder and dest.is_dir():
        raise SaveError("the destination is a folder, not a file: %s" % dest)
    cache_folder = entry.outputs[0].parent
    for src, tgt in pairs:
        if _inside(tgt, cache_folder) or os.path.abspath(src) == os.path.abspath(tgt):
            raise SaveError("cannot save into the cache or onto the source itself: %s" % tgt)
    conflicts = [t for _, t in pairs if t.exists()]
    if conflicts and not overwrite:
        raise SaveConflict(conflicts)
    created = is_folder and not dest.exists()
    temps = []
    try:
        for _, tgt in pairs:
            tgt.parent.mkdir(parents=True, exist_ok=True)
        for src, tgt in pairs:
            tmp = tgt.with_name(tgt.name + TMP_SUFFIX)
            temps.append(tmp)
            shutil.copy2(src, tmp)
        for (_, tgt), tmp in zip(pairs, temps):
            os.replace(tmp, tgt)
    except OSError as e:
        for tmp in temps:
            if tmp.exists():
                tmp.unlink()
        if created:
            shutil.rmtree(dest, ignore_errors=True)
        raise SaveError("cannot save: %s" % e)
    return [t for _, t in pairs]


@dataclass(frozen=True)
class JobResult:
    ok: bool
    status: Literal["ok", "failed", "cancelled", "timeout", "invalid"]
    entry: Entry | None
    from_cache: bool
    run: RunResult | None
    error: str = ""
    param: str = ""
    warning: str = ""
    elapsed: float = 0.0
    transient: bool = field(default=False, repr=False)     # the entry lives in the run's temp folder (not cached)

    def tail(self, n: int = 20) -> str:
        return self.run.tail(n) if self.run else ""

    def cleanup(self) -> None:
        """Remove the temp folder of an uncached result; nothing to do otherwise."""
        if self.transient and self.run is not None:
            self.run.cleanup()


class JobService:
    def __init__(self, cache: Cache, generators_dir: Path = GENERATORS_DIR, python: str | None = None):
        self.cache = cache
        self.generators_dir = Path(generators_dir)
        self.python = python
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _lock_for(self, key: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())

    def get(self, part: Part, raw: Mapping | None = None, *, cancel: CancelToken | None = None,
            timeout: float | None = None, on_line: Callable[[str], None] | None = None) -> JobResult:
        start = time.monotonic()

        def done(**kw):
            kw.setdefault("elapsed", time.monotonic() - start)
            return JobResult(**kw)

        try:
            params = part.normalise(raw)
        except ParamError as e:
            return done(ok=False, status="invalid", entry=None, from_cache=False, run=None, error=str(e.message), param=e.param)
        try:
            hit = self.cache.lookup(part, params)
            if hit is not None:
                return done(ok=True, status="ok", entry=hit, from_cache=True, run=None)
            if part.seed_for(params):
                raise CacheError("seed file missing: %s" % part.seed_for(params))
            with self._lock_for(self.cache.key(part, params)):
                hit = self.cache.lookup(part, params)
                if hit is not None:
                    return done(ok=True, status="ok", entry=hit, from_cache=True, run=None)
                run = run_part(part, params, self.generators_dir, python=self.python, cancel=cancel, timeout=timeout,
                               on_line=on_line)
                if not run.ok:
                    return done(ok=False, status=run.status, entry=None, from_cache=False, run=run, error=run.error)
                try:
                    entry = self.cache.store(part, params, run)
                except CacheError as e:
                    entry = Entry("", part.key, dict(params), run.outputs, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                  run.elapsed, run.tail(1), self.cache.generator, 0)
                    return done(ok=True, status="ok", entry=entry, from_cache=False, run=run, transient=True,
                                warning="%s; the model was generated but not cached" % e)
                run.cleanup()
                return done(ok=True, status="ok", entry=entry, from_cache=False, run=run)
        except CacheError as e:
            return done(ok=False, status="failed", entry=None, from_cache=False, run=None, error=str(e))
