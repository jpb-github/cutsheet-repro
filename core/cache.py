"""Cache of generated models: key = part type + normalised parameters + generator version.

Layout of the root folder: entries/<key>/ (the outputs and meta.json), tmp/ (entries being written). An entry becomes
visible by one directory rename, so a reader never sees a half-written entry. Standard library only (plus core.catalogue
and core.runner for the types).
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from core.catalogue import Part
from core.runner import GENERATORS_DIR, RunResult

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"


def environment_tag() -> str:
    """The Python version (a cached result is only reused by the same interpreter)."""
    return "py%d.%d" % (sys.version_info[0], sys.version_info[1])


def _file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def generator_version(generators_dir: Path) -> str:
    """Hash of every bundled generator file (path and content, no __pycache__) plus the environment tag."""
    root = Path(generators_dir)
    lines = []
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            parts = p.relative_to(root).parts
            if p.is_file() and "__pycache__" not in parts:
                lines.append("%s\0%s\n" % (p.relative_to(root).as_posix(), _file_sha(p)))
    h = hashlib.sha256("".join(lines).encode("utf-8"))
    h.update(environment_tag().encode("utf-8"))
    return h.hexdigest()[:40]


def cache_key(type_key: str, params: Mapping[str, object], generator: str) -> str:
    text = json.dumps({"type": type_key, "params": params, "generator": generator}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()[:40]


def default_cache_dir() -> Path:
    override = os.environ.get("CUTSHEET_CACHE_DIR")
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "CutsheetGenerator" / "cache"


class CacheError(Exception):
    pass


@dataclass(frozen=True)
class Entry:
    key: str
    type: str
    params: dict
    outputs: tuple[Path, ...]
    created: str
    duration: float
    last_line: str
    generator: str
    size: int
    is_seed: bool = False


def _tree_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else 0


class Cache:
    def __init__(self, root: Path, generators_dir: Path = GENERATORS_DIR, seed_dir: Path = SEED_DIR):
        self.root = Path(root)
        self.generators_dir = Path(generators_dir)
        self.seed_dir = Path(seed_dir)
        self._generator: str | None = None

    @classmethod
    def default(cls) -> "Cache":
        return cls(default_cache_dir())

    @property
    def generator(self) -> str:
        if self._generator is None:
            self._generator = generator_version(self.generators_dir)
        return self._generator

    def key(self, part: Part, raw: Mapping | None = None) -> str:
        return cache_key(part.key, part.normalise(raw), self.generator)

    def _read(self, folder: Path, key: str) -> Entry | None:
        """The entry stored in folder, or None (and the folder removed) when it is missing or damaged."""
        if not folder.is_dir():
            return None
        try:
            meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
            if meta["key"] != key:
                raise ValueError("key mismatch")
            outputs = tuple(folder / n for n in meta["outputs"])
            if not outputs or not all(o.exists() for o in outputs):
                raise ValueError("missing output")
            return Entry(key, meta["type"], meta["params"], outputs, meta["created"], float(meta["duration"]),
                         meta["last_line"], meta["generator"], int(meta["size"]))
        except (OSError, ValueError, KeyError, TypeError):
            shutil.rmtree(folder, ignore_errors=True)
            return None

    def lookup(self, part: Part, raw: Mapping | None = None) -> Entry | None:
        name = part.seed_for(part.normalise(raw))
        if name:
            seed = self.seed_dir / name
            if not seed.is_file():
                raise CacheError("seed file missing: %s" % name)
            return Entry("seed:" + name, part.key, part.normalise(raw), (seed,), "", 0.0, "", "", seed.stat().st_size, True)
        key = self.key(part, raw)
        return self._read(self.root / "entries" / key, key)

    def store(self, part: Part, raw: Mapping | None, result: RunResult) -> Entry:
        params = part.normalise(raw)
        if part.seed_for(params):
            raise CacheError("%s is a fixed part, nothing to store" % part.key)
        if not result.ok or result.work_dir is None:
            raise CacheError("only successful runs are cached")
        key = cache_key(part.key, params, self.generator)
        names = part.output_names(params)
        final = self.root / "entries" / key
        tmp = None
        try:
            (self.root / "tmp").mkdir(parents=True, exist_ok=True)
            (self.root / "entries").mkdir(parents=True, exist_ok=True)
            tmp = Path(tempfile.mkdtemp(dir=self.root / "tmp"))
            for name in names:
                src = Path(result.work_dir) / name
                if src.is_dir():
                    shutil.copytree(src, tmp / name)
                else:
                    shutil.copy2(src, tmp / name)
            meta = {"key": key, "type": part.key, "params": params, "generator": self.generator,
                    "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "duration": result.elapsed,
                    "last_line": result.tail(1), "outputs": list(names), "size": sum(_tree_size(tmp / n) for n in names)}
            (tmp / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
            try:
                os.rename(tmp, final)
            except (FileExistsError, PermissionError):
                if not final.exists():
                    raise
                shutil.rmtree(tmp, ignore_errors=True)
                existing = self._read(final, key)
                if existing is None:
                    raise CacheError("cannot write the cache: an unreadable entry is in the way")
                return existing
        except OSError as e:
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)
            raise CacheError("cannot write the cache: %s" % e)
        return self._read(final, key)

    def entries(self) -> list[Entry]:
        """Valid entries, newest first; damaged ones are removed."""
        folder = self.root / "entries"
        found = [e for e in (self._read(p, p.name) for p in (sorted(folder.iterdir()) if folder.is_dir() else [])) if e]
        return sorted(found, key=lambda e: e.created, reverse=True)

    def size(self) -> int:
        """Bytes of everything the cache wrote (entries and temp folders), nothing else."""
        return sum(_tree_size(self.root / name) for name in ("entries", "tmp"))

    def clear(self) -> int:
        """Remove entries/ and tmp/ (never the root or other files); returns the bytes freed."""
        freed, errors = 0, []
        for name in ("entries", "tmp"):
            folder = self.root / name
            if not folder.is_dir():
                continue
            before = _tree_size(folder)
            try:
                shutil.rmtree(folder)
                freed += before
            except OSError as e:
                errors.append(str(e))
                freed += before - _tree_size(folder)
        if errors:
            raise CacheError("cannot clear the cache: %s" % "; ".join(errors))
        return freed
