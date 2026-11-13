"""The guillotine packer: one deterministic run, the cut tree, and the checker that proves a layout."""
import itertools

import pytest

from core.cutting import (Cut, CutError, Item, Placed, Rect, Sheet, SheetLayout, Variant, check_layout, pack)

SHEET = Sheet(2400, 1200)
DEFAULT = Variant("short", "short", "area", 0)


def example_items():
    """The seven distinct pieces of the example block (760 x 350 x 540, 2 drawers), expanded, thick ones on one sheet."""
    sizes = [("A", 760, 540, 2), ("B", 760, 350, 2), ("C", 540, 350, 2), ("D", 700, 200, 4), ("E", 330, 180, 4),
             ("F", 512, 180, 4), ("G", 760, 300, 2)]
    return [Item("%s%d" % (name, i + 1), length, width) for name, length, width, qty in sizes for i in range(qty)]


def test_one_piece_the_size_of_the_sheet_needs_no_cut():
    layouts = pack([Item("A1", 2400, 1200)], SHEET, 5, DEFAULT)
    assert len(layouts) == 1
    assert layouts[0].cuts == ()
    assert layouts[0].placed == (Placed("A1", 0, 0, 2400, 1200, False),)
    assert layouts[0].waste == 0


def test_piece_filling_a_free_rectangle_exactly_makes_no_second_cut():
    # 1195 + kerf 5 = 1200: after the first cut the strip is exactly the piece wide, only one cut is needed for it.
    items = [Item("A1", 2400, 595), Item("B1", 2400, 600)]
    layouts = pack(items, SHEET, 5, DEFAULT)
    assert len(layouts) == 1
    assert len(layouts[0].cuts) == 1
    assert check_layout(layouts, items, SHEET, 5) == []


def test_three_identical_pieces_on_a_sheet_that_holds_two():
    sheet = Sheet(1000, 500)
    items = [Item("A%d" % i, 600, 480) for i in (1, 2, 3)]
    layouts = pack(items, sheet, 5, DEFAULT)
    assert check_layout(layouts, items, sheet, 5) == []
    # 600 x 480 pieces: one per sheet on 1000 x 500 (side by side 1200 > 1000, stacked 960 > 500 even rotated)
    assert len(layouts) == 3


def test_two_pieces_fit_next_to_each_other_when_the_sheet_holds_two():
    sheet = Sheet(1250, 500)
    items = [Item("A1", 600, 480), Item("A2", 600, 480), Item("A3", 600, 480)]
    layouts = pack(items, sheet, 5, DEFAULT)
    assert len(layouts) == 2
    assert check_layout(layouts, items, sheet, 5) == []


def test_sliver_narrower_than_the_kerf_is_waste_and_never_negative():
    sheet = Sheet(1000, 500)
    items = [Item("A1", 997, 500)]  # leftover 3 < kerf 5
    layouts = pack(items, sheet, 5, DEFAULT)
    assert len(layouts) == 1
    assert len(layouts[0].cuts) == 1
    assert layouts[0].largest_offcut == 0
    assert check_layout(layouts, items, sheet, 5) == []


def test_piece_that_fits_only_rotated():
    sheet = Sheet(1000, 300)
    items = [Item("A1", 250, 900)]
    layouts = pack(items, sheet, 5, DEFAULT)
    assert layouts[0].placed[0].rotated is True
    assert (layouts[0].placed[0].w, layouts[0].placed[0].h) == (900, 250)
    assert check_layout(layouts, items, sheet, 5) == []


def test_piece_bigger_than_the_sheet_in_both_orientations_raises():
    with pytest.raises(CutError) as e:
        pack([Item("A1", 2500, 1300)], SHEET, 5, DEFAULT)
    assert "A1" in str(e.value)
    with pytest.raises(CutError):
        pack([Item("A1", 1300, 1300)], SHEET, 5, DEFAULT)


def test_twenty_identical_pieces():
    items = [Item("A%d" % i, 300, 200) for i in range(20)]
    layouts = pack(items, SHEET, 5, DEFAULT)
    assert len(layouts) == 1
    assert check_layout(layouts, items, SHEET, 5) == []


@pytest.mark.parametrize("select,split,order", list(itertools.product(
    ("short", "long", "area", "worst_area"), ("short", "long", "min_area", "max_area"), ("area", "long", "shuffle"))))
def test_every_variant_gives_a_valid_layout_on_the_example(select, split, order):
    items = example_items()
    for sheet in (SHEET, Sheet(1200, 1200), Sheet(900, 700)):
        layouts = pack(items, sheet, 5, Variant(select, split, order, 7))
        assert check_layout(layouts, items, sheet, 5) == []


def test_same_variant_same_result():
    items = example_items()
    v = Variant("long", "min_area", "shuffle", 3)
    assert pack(items, SHEET, 5, v) == pack(items, SHEET, 5, v)


def test_cut_numbers_are_one_to_n_ordered_by_stage():
    layouts = pack(example_items(), SHEET, 5, DEFAULT)
    for layout in layouts:
        assert [c.number for c in layout.cuts] == list(range(1, len(layout.cuts) + 1))
        stages = [c.stage for c in layout.cuts]
        assert stages == sorted(stages)
        assert stages[0] == 1


def test_waste_is_sheet_area_minus_pieces():
    items = example_items()
    layouts = pack(items, SHEET, 5, DEFAULT)
    placed = sum(p.w * p.h for layout in layouts for p in layout.placed)
    assert sum(layout.waste for layout in layouts) == pytest.approx(len(layouts) * 2400 * 1200 - placed)


def test_check_layout_finds_problems():
    items = [Item("A1", 500, 400), Item("B1", 500, 400)]
    sheet = Sheet(1200, 500)
    good = pack(items, sheet, 5, DEFAULT)
    assert check_layout(good, items, sheet, 5) == []
    a, b = good[0].placed
    # overlap
    bad = SheetLayout((a, Placed(b.label, a.x + 10, a.y, b.w, b.h, b.rotated)), good[0].cuts, 0, 0)
    assert any("overlap" in m for m in check_layout([bad], items, sheet, 5))
    # outside the sheet
    bad = SheetLayout((a, Placed(b.label, 1000, a.y, b.w, b.h, b.rotated)), good[0].cuts, 0, 0)
    assert any("outside" in m for m in check_layout([bad], items, sheet, 5))
    # two pieces closer than the kerf
    bad = SheetLayout((a, Placed(b.label, a.x + a.w + 2, a.y, b.w, b.h, b.rotated)), good[0].cuts, 0, 0)
    assert any("kerf" in m for m in check_layout([bad], items, sheet, 5))
    # a missing piece and a doubled one
    assert any("missing" in m for m in check_layout([SheetLayout((a,), (), 0, 0)], items, sheet, 5))
    assert any("twice" in m for m in check_layout([SheetLayout((a, a), (), 0, 0)], items, sheet, 5))
    # a cut that crosses a piece
    cut = Cut(1, 1, True, a.x + a.w / 2, Rect(0, 0, 1200, 500))
    bad = SheetLayout(good[0].placed, (cut,), 0, 0)
    assert any("cut" in m for m in check_layout([bad], items, sheet, 5))
