"""The search: many variants, process pool, refine. No clock: iterations and a seed make results reproducible."""
import os

import pytest

from core import cutting
from core.cutting import Item, Sheet, Solution, check_layout, default_workers, optimize, pack, score, Variant
from core.drawer_rules import plan_drawer_block

DEFAULTS = dict(width=760, height=350, depth=540, box_clearance=4, drawers=2, drawer_clearance=5, thick=18, thin=6,
                slide_thickness=12, slide_length=500, slide_height=35, slide_clearance=0.5)


def items_of(material):
    out = []
    for p in plan_drawer_block(**DEFAULTS):
        if p.material == material:
            out += [Item("%s%d" % (p.name, i + 1), p.length, p.width) for i in range(p.qty)]
    return out


def test_default_workers(monkeypatch):
    for cpus, expected in ((1, 1), (4, 3), (16, 12), (None, 1)):
        monkeypatch.setattr(os, "cpu_count", lambda c=cpus: c)
        assert default_workers() == expected


def test_score_orders_sheets_first_then_waste():
    items = items_of("thick")
    a = pack(items, Sheet(2400, 1200), 5, Variant("short", "short", "area", 0))
    b = pack(items, Sheet(1200, 1200), 5, Variant("short", "short", "area", 0))
    assert score(a)[0] == len(a)
    assert score(a) < score(b) if len(a) < len(b) else True
    assert len(score(a)) == 4


def test_example_fits_one_sheet_per_material_on_2400_x_1200():
    sheet = Sheet(2400, 1200)
    for material in ("thick", "thin"):
        items = items_of(material)
        sol = optimize(items, sheet, 5, iterations=40, workers=1)
        assert len(sol.layouts) == 1, material
        assert check_layout(sol.layouts, items, sheet, 5) == []


def test_example_thick_needs_more_sheets_when_small_and_stays_valid():
    sheet = Sheet(1200, 1200)
    items = items_of("thick")
    sol = optimize(items, sheet, 5, iterations=40, workers=1)
    assert len(sol.layouts) == 2
    assert check_layout(sol.layouts, items, sheet, 5) == []


def test_pieces_spread_over_several_sheets_when_they_do_not_fit_one():
    sheet = Sheet(1000, 600)
    items = [Item("P%d" % i, 900, 500) for i in range(5)]
    sol = optimize(items, sheet, 5, iterations=10, workers=1)
    assert len(sol.layouts) == 5
    assert check_layout(sol.layouts, items, sheet, 5) == []


def test_same_seed_same_score_with_one_and_two_workers():
    items = items_of("thick")
    sheet = Sheet(1200, 1200)
    one = optimize(items, sheet, 5, iterations=60, workers=1, seed=3)
    two = optimize(items, sheet, 5, iterations=60, workers=2, seed=3)
    assert one.score == two.score
    assert one.layouts == two.layouts


def test_never_worse_than_start_and_bad_start_is_improved():
    items = items_of("thick")
    sheet = Sheet(2400, 1200)
    bad_layouts = pack(items, sheet, 5, Variant("worst_area", "max_area", "shuffle", 99))
    bad = Solution(tuple(bad_layouts), score(bad_layouts))
    best = optimize(items, sheet, 5, iterations=40, workers=1)
    assert optimize(items, sheet, 5, iterations=1, workers=1, start=best).score == best.score
    improved = optimize(items, sheet, 5, iterations=40, workers=1, start=bad)
    assert improved.score <= bad.score
    assert improved.score <= best.score or improved.score == best.score


def test_on_progress_scores_strictly_improve():
    seen = []
    optimize(items_of("thick"), Sheet(1200, 1200), 5, iterations=80, workers=1, on_progress=seen.append)
    scores = [s.score for s in seen]
    assert all(b < a for a, b in zip(scores, scores[1:]))


def test_cancel_returns_the_first_result():
    items = items_of("thick")
    sheet = Sheet(1200, 1200)
    sol = optimize(items, sheet, 5, iterations=1000, workers=1, cancel=lambda: True)
    first = pack(items, sheet, 5, cutting.variant_for(0, 0))
    assert sol.score == score(first)


def test_pool_that_cannot_start_falls_back_to_the_calling_process(monkeypatch):
    class Broken:
        def __init__(self, *a, **k):
            raise OSError("no processes here")

    monkeypatch.setattr(cutting, "ProcessPoolExecutor", Broken)
    items = items_of("thick")
    sol = optimize(items, Sheet(1200, 1200), 5, iterations=20, workers=4)
    assert check_layout(sol.layouts, items, Sheet(1200, 1200), 5) == []


def test_item_that_fits_nowhere_raises():
    with pytest.raises(cutting.CutError):
        optimize([Item("X", 3000, 2000)], Sheet(2400, 1200), 5, iterations=5, workers=1)
