"""Build the Cutsheet Generator MSI.

Usage: python installer/build_msi.py [--out installer/output] [--stage installer/stage] [--version X.Y.Z]
Stages the files the installer ships (app, core, generators, seed files, the launcher, requirements, README, VERSION; no
tests, docs, STL, bytecode), then runs WiX (a dotnet tool) on installer/cutsheet.wxs and writes
<out>/CutsheetGenerator-<version>.msi. One-time tool setup:
  dotnet tool install --global wix --version 5.0.2
  wix extension add --global WixToolset.Util.wixext/5.0.2
Exit codes: 0 built, 1 build failed, 2 bad version or WiX missing.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

APP = Path(__file__).resolve().parent.parent
TOP_FOLDERS = ("app", "core", "generators", "seed", "installer/launcher")
TOP_FILES = ("requirements.txt", "bundle_manifest.json", "README.md", "VERSION")
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".stl"}
WIX_HINT = ("WiX was not found. Install it once with:\n  dotnet tool install --global wix --version 5.0.2\n"
            "  wix extension add --global WixToolset.Util.wixext/5.0.2\n"
            "and make sure %USERPROFILE%\\.dotnet\\tools is on PATH.")


def read_version(path: Path) -> str:
    text = Path(path).read_text(encoding="utf-8").strip()
    parts = text.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError("VERSION must be three numbers like 1.0.0, got %r" % text)
    return text


def stage(app_dir: Path, stage_dir: Path) -> list[str]:
    """Recreate stage_dir with the files to ship; returns their relative POSIX paths."""
    app_dir, stage_dir = Path(app_dir), Path(stage_dir)
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)
    staged = []

    def add(src: Path) -> None:
        rel = src.relative_to(app_dir)
        dest = stage_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        staged.append(rel.as_posix())

    for top in TOP_FOLDERS:
        base = app_dir / top
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                rel_parts = p.relative_to(base).parts
                if p.is_file() and not SKIP_DIRS.intersection(rel_parts) and p.suffix.lower() not in SKIP_SUFFIXES:
                    add(p)
    for name in TOP_FILES:
        if (app_dir / name).is_file():
            add(app_dir / name)
    return staged


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(APP / "installer" / "output"))
    ap.add_argument("--stage", default=str(APP / "installer" / "stage"))
    ap.add_argument("--version", default=None, help="default: the VERSION file")
    args = ap.parse_args(argv)
    wix = shutil.which("wix")
    if wix is None:
        sys.stderr.write(WIX_HINT + "\n")
        return 2
    try:
        version = args.version or read_version(APP / "VERSION")
        read_version_text = version.split(".")
        if len(read_version_text) != 3 or not all(p.isdigit() for p in read_version_text):
            raise ValueError("version must be three numbers like 1.0.0, got %r" % version)
    except (OSError, ValueError) as e:
        sys.stderr.write("error: %s\n" % e)
        return 2
    staged = stage(APP, Path(args.stage))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    msi = out / ("CutsheetGenerator-%s.msi" % version)
    cmd = [wix, "build", str(APP / "installer" / "cutsheet.wxs"), "-arch", "x64", "-ext", "WixToolset.Util.wixext",
           "-d", "StageDir=%s" % Path(args.stage), "-d", "Version=%s" % version, "-o", str(msi)]
    print("staged %d files; running wix build" % len(staged))
    rc = subprocess.run(cmd).returncode
    if rc != 0 or not msi.is_file():
        sys.stderr.write("error: wix build failed (exit %d)\n" % rc)
        return 1
    print("OK -> %s (%.1f MB)" % (msi, msi.stat().st_size / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
