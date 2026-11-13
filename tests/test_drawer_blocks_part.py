import subprocess
import sys
from pathlib import Path

import pytest

from core.catalogue import PARTS, get_part
from core.drawer_rules import pieces_to_csv
from core.catalogue import drawer_block_pieces
from core.params import ParamError

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "generators" / "DrawerBlocks" / "skills" / "drawer-blocks-generator" / "scripts"
PART = get_part("drawer_blocks")


def test_the_rules_of_the_generator_are_an_exact_copy_of_the_core():
    assert (SCRIPTS / "d02_rules.py").read_bytes() == (ROOT / "core" / "drawer_rules.py").read_bytes()


def test_the_part_is_registered_with_the_defaults_of_the_spreadsheet():
    assert list(PARTS) == ["drawer_blocks"] and PART.tab == "drawer_blocks"
    p = PART.normalise({})
    assert p["drawers"] == 2 and p["width"] == "760mm" and p["slide_height"] == "35mm" and p["slide_clearance"] == "0.5mm"
    assert PART.output_names(p) == ("Drawer Blocks - 2 drawers 760x350x540.csv",)
    assert [x.qty for x in drawer_block_pieces(p)] == [2, 2, 1, 4, 4, 2, 2]


def test_equal_requests_share_one_canonical_form():
    assert PART.normalise({"width": "76cm", "height": "350"}) == PART.normalise({"width": "760mm"})
    assert PART.normalise({"depth": "21.259842519685in"})["depth"] == "540mm"


@pytest.mark.parametrize("raw, param", [({"slide_height": "142"}, "slide_height"), ({"drawers": "40"}, "drawers"),
                                         ({"slide_length": "600"}, "slide_length"), ({"thin": "1"}, "thin"), ({"drawers": "x"}, "drawers")])
def test_invalid_requests_are_param_errors(raw, param):
    with pytest.raises(ParamError) as e:
        PART.normalise(raw)
    assert e.value.param == param


def test_the_command_line_writes_the_csv(tmp_path):
    p = PART.normalise({})
    inv = PART.invocation(p, tmp_path)
    r = subprocess.run([sys.executable, str(SCRIPTS / "build_cutlist.py"), *inv.args], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and r.stdout.strip().splitlines()[-1] == "OK"
    assert (tmp_path / inv.outputs[0]).read_text(encoding="utf-8") == pieces_to_csv(drawer_block_pieces(p))


def test_a_failed_request_is_reported_and_writes_nothing(tmp_path):
    inv = PART.invocation(PART.normalise({}), tmp_path)
    args = list(inv.args)
    args[args.index("--slide-height") + 1] = "200"
    r = subprocess.run([sys.executable, str(SCRIPTS / "build_cutlist.py"), *args], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 1 and r.stdout.strip().splitlines()[-1].startswith("FAILED: slide_height")
    assert not (tmp_path / inv.outputs[0]).exists()
