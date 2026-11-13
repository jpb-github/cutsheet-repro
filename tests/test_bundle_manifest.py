import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sync_generators  # noqa: E402


def test_the_manifest_matches_the_generators():
    """Editing anything under generators/ changes the generator version of the cache: it must be deliberate (sync_generators.py --update-manifest)."""
    assert sync_generators.check(ROOT) == []
