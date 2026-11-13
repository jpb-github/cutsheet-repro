"""The data of the cutsheet: labels, sheets with placed pieces and cuts, instructions, pocket screw marks."""
import pytest

from core import catalogue, cutting
from core.cutsheet import PocketEdge, build_cutsheet, label_names, plan_cutsheet
from core.cutting import check_layout

PART = catalogue.get_part("drawer_blocks")


def example(**raw):
    p = PART.normalise(raw)
    pieces = catalogue.drawer_block_pieces(p)
    hardware = catalogue.drawer_block_hardware(p)
    solutions = plan_cutsheet(p, iterations=30, workers=1)
    return p, pieces, hardware, build_cutsheet(pieces, hardware, p, solutions)


def test_label_names():
    assert label_names(3) == ["A", "B", "C"]
    names = label_names(30)
    assert names[25] == "Z" and names[26] == "AA" and names[27] == "AB" and len(set(names)) == 30


def test_example_labels_a_to_g():
    p, pieces, hardware, sheet = example()
    assert [l.label for l in sheet.labels] == list("ABCDEFG")
    assert [l.piece.name for l in sheet.labels] == [x.name for x in pieces]


def test_one_thick_and_one_thin_sheet_with_every_piece_once():
    p, pieces, hardware, cs = example()
    assert [(s.material, s.number) for s in cs.sheets] == [("thick", 1), ("thin", 2)]
    placed = sorted(pl.label for s in cs.sheets for pl in s.placed)
    expected = []
    for l in cs.labels:
        expected += [l.label] if l.piece.qty == 1 else ["%s%d" % (l.label, i + 1) for i in range(l.piece.qty)]
    assert placed == sorted(expected)


def test_plan_gives_valid_layouts_per_material():
    p = PART.normalise({})
    solutions = plan_cutsheet(p, iterations=20, workers=1)
    assert set(solutions) == {"thick", "thin"}
    for material, sol in solutions.items():
        assert sol.layouts


def test_two_thick_sheets_on_small_sheets():
    p, pieces, hardware, cs = example(sheet_length="1200mm", sheet_width="1200mm")
    assert [s.material for s in cs.sheets].count("thick") == 2
    assert cs.summary()["sheets"] == {"thick": 2, "thin": 1}


def test_pocket_marks_of_drawer_front_and_box_side():
    p, pieces, hardware, cs = example()
    by_name = {l.piece.name: l.label for l in cs.labels}
    front = cs.pocket_marks(by_name["Drawer front and back"])
    assert [e.edge for e in front] == ["left", "right"]
    width = next(x.width for x in pieces if x.name == "Drawer front and back")
    assert width == pytest.approx(141.5)
    assert front[0] == PocketEdge("left", (35.375, 106.125))
    side = cs.pocket_marks(by_name["Box side"])
    assert [e.edge for e in side] == ["left", "right"]
    assert side[0].offsets == (51.2, 153.6, 256.0, 358.4, 460.8)
    assert cs.pocket_marks(by_name["Facade"]) == []
    assert cs.pocket_marks(by_name["Box side"] + "2") == side      # a copy has the marks of its piece


def test_total_marks_equal_the_screw_counts():
    p, pieces, hardware, cs = example()
    total = {"box": 0, "drawers": 0}
    for l in cs.labels:
        n = sum(len(e.offsets) for e in cs.pocket_marks(l.label)) * l.piece.qty
        if l.piece.name == "Box side":
            total["box"] += n
        elif l.piece.name == "Drawer front and back":
            total["drawers"] += n
    counts = {h.name: h.qty for h in hardware}
    assert total["box"] == counts["Pocket screw, box"] == 20
    assert total["drawers"] == counts["Pocket screw, drawers"] == 16


def test_instructions_one_per_cut_with_the_right_distance():
    p, pieces, hardware, cs = example()
    for s in cs.sheets:
        lines = s.instructions()
        assert len(lines) == len(s.cuts)
        for line, cut in zip(lines, s.cuts):
            assert line.startswith("Cut %d:" % cut.number)
            d = cut.at - (cut.rect.x if cut.vertical else cut.rect.y)
            assert ("%g" % round(d, 3)) in line
    first = cs.sheets[0].instructions()[0]
    assert "whole" in first and "2400 x 1200" in first


def test_waste_percent_between_0_and_100():
    p, pieces, hardware, cs = example()
    summary = cs.summary()
    assert len(summary["waste"]) == len(cs.sheets)
    for number, material, percent in summary["waste"]:
        assert 0 <= percent <= 100


def test_layouts_of_the_cutsheet_are_sound():
    p, pieces, hardware, cs = example()
    for s in cs.sheets:
        items = [cutting.Item(pl.label, pl.w if not pl.rotated else pl.h, pl.h if not pl.rotated else pl.w) for pl in s.placed]
        layout = cutting.SheetLayout(s.placed, s.cuts, 0, 0)
        assert check_layout([layout], items, cutting.Sheet(s.length, s.width), 5) == []


def test_refine_start_never_worse():
    p = PART.normalise({})
    first = plan_cutsheet(p, iterations=10, workers=1)
    again = plan_cutsheet(p, iterations=10, workers=1, seed=1, start=first)
    for material in first:
        assert again[material].score <= first[material].score


def test_cancel_still_returns_a_result():
    p = PART.normalise({})
    sols = plan_cutsheet(p, iterations=500, workers=1, cancel=lambda: True)
    assert set(sols) == {"thick", "thin"}
