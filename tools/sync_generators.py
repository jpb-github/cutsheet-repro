"""Check (or refresh) the hash manifest of the generator bundle of the Cutsheet Generator.

Usage: python tools/sync_generators.py [--check | --update-manifest] [--smoke]

generators/   the generator scripts and reference STEP files; since the repository folders were dropped this is the
              SOURCE: edit the scripts here, then run --update-manifest
bundle_manifest.json   sha256 of every bundled file ("generators/<rel>", forward slashes)

--check            (default) report files that differ from the manifest, are missing or are extra; exit 1 on drift
--update-manifest  rewrite bundle_manifest.json from the files on disk (after a deliberate edit)
--smoke            when in sync, run tools/check_bundle.py (isolated smoke test of the bundle)

Never part of the bundle: *.stl (protected inputs), *.pyc, __pycache__. Editing anything under generators/ changes the
generator version of the cache and invalidates every cached result.
Exit code: 0 in sync / done, 1 drift or error.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"__pycache__"}
MANIFEST = "bundle_manifest.json"
TEXT_SUFFIXES = {".py", ".step", ".stp", ".json", ".md", ".txt"}


def _sha(path: Path) -> str:
    """sha256 of the content; text files with CRLF read as LF, so the hash is the same in any git checkout."""
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(bytes([13, 10]), bytes([10]))
    return hashlib.sha256(data).hexdigest()


def _manifest_of(root: Path) -> dict:
    out = {}
    for sub in ("generators", "seed"):  # seed/ is optional: fixed STEP files, none yet
        base = root / sub
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.is_file() and p.name != ".gitkeep" and p.suffix.lower() != ".pyc"                         and not SKIP_DIRS.intersection(p.relative_to(base).parts):
                    out[p.relative_to(root).as_posix()] = _sha(p)
    return out


def check(bundle: Path) -> list:
    """One line per difference between the files on disk and the manifest; [] = in sync."""
    bundle = Path(bundle)
    mf = bundle / MANIFEST
    recorded = json.loads(mf.read_text(encoding="utf-8")) if mf.is_file() else {}
    actual = _manifest_of(bundle)
    lines = []
    for k in sorted(set(actual) | set(recorded)):
        if k not in actual:
            lines.append("missing: %s" % k)
        elif k not in recorded:
            lines.append("extra: %s" % k)
        elif actual[k] != recorded[k]:
            lines.append("modified: %s" % k)
    return lines


def update_manifest(bundle: Path) -> dict:
    bundle = Path(bundle)
    manifest = _manifest_of(bundle)
    (bundle / MANIFEST).write_text(json.dumps(manifest, indent=1, sort_keys=True) + chr(10), encoding="utf-8", newline=chr(10))
    return manifest


def _smoke() -> int:
    try:
        import check_bundle
    except ImportError:
        print("smoke test not available")
        return 1
    return check_bundle.main([])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bundle", default=str(APP), help="folder holding generators/, bundle_manifest.json (default: this app)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="report drift against the manifest (default)")
    g.add_argument("--update-manifest", action="store_true", help="rewrite the manifest from the files on disk")
    ap.add_argument("--smoke", action="store_true", help="when in sync, run tools/check_bundle.py on this app's bundle")
    a = ap.parse_args(argv)
    bundle = Path(a.bundle)
    if a.update_manifest:
        m = update_manifest(bundle)
        print("manifest updated: %d files" % len(m))
    else:
        lines = check(bundle)
        for l in lines:
            print(l)
        print("in sync" if not lines else "%d difference(s)" % len(lines))
        if lines:
            return 1
    return _smoke() if a.smoke else 0


if __name__ == "__main__":
    sys.exit(main())
