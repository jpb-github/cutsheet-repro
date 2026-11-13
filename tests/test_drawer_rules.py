import csv

import pytest

from core.drawer_rules import (DrawerError, Hardware, Piece, per_joint, pieces_to_csv, plan_drawer_block, plan_hardware,
                               pocket_screw_length)

DEFAULTS = dict(width=760, height=350, depth=540, box_clearance=4, drawers=2, drawer_clearance=5, thick=18, thin=6,
                slide_thickness=12, slide_length=500, slide_height=35, slide_clearance=0.5)
SPACING = 150


def plan(**kw):
    return plan_drawer_block(**{**DEFAULTS, **kw})


def by_name(pieces):
    return {p.name: p for p in pieces}


def test_the_example_of_the_spreadsheet():
    got = [(p.name, p.material, p.qty, p.length, p.width) for p in plan()]
    assert got == [
        ("Box top and bottom", "thick", 2, 756, 512),
        ("Box side", "thick", 2, 310, 512),
        ("Box back", "thin", 1, 756, 346),
        ("Drawer side", "thick", 4, 500, 141.5),
        ("Drawer front and back", "thick", 4, 658, 141.5),
        ("Drawer bottom", "thin", 2, 694, 500),
        ("Facade", "thick", 2, 756, 165.5),
    ]
    assert [p.thickness for p in plan()] == [18, 18, 6, 18, 18, 6, 18]


def test_one_and_three_drawers():
    one = by_name(plan(drawers=1))
    assert one["Drawer side"].qty == 2
    assert one["Drawer side"].width == (310 - 10) - 6          # one drawer fills the inside less two gaps, minus the bottom
    assert one["Facade"].width == 346 - 10 and one["Facade"].qty == 1
    three = by_name(plan(drawers=3))
    assert three["Drawer front and back"].qty == 6 and three["Drawer bottom"].qty == 3
    assert three["Facade"].width == pytest.approx((346 - 20) / 3, abs=0.001)
    assert three["Drawer side"].width == pytest.approx((310 - 20) / 3 - 6, abs=0.001)


def test_the_slide_clearance_narrows_the_drawer():
    wide = by_name(plan(slide_clearance=0))
    assert wide["Drawer bottom"].length == 696 and wide["Drawer front and back"].length == 660
    assert by_name(plan(slide_clearance=1))["Drawer bottom"].length == 692


@pytest.mark.parametrize("change, param", [
    ({"drawers": 0}, "drawers"),
    ({"drawers": 30}, "drawers"),                       # the drawers would have no height
    ({"slide_height": 142}, "slide_height"),           # higher than the drawer side (141.5)
    ({"slide_length": 513}, "slide_length"),           # longer than the box depth (512)
    ({"thick": 200}, "thick"),                          # no width left in the box
    ({"thin": 600}, "thin"),                            # no depth left
    ({"slide_thickness": 350}, "slide_thickness"),      # no width left in the drawer
    ({"width": 40}, "width"),
    ({"slide_height": 0}, "slide_height"),
])
def test_invalid_requests_name_the_parameter(change, param):
    with pytest.raises(DrawerError) as e:
        plan(**change)
    assert e.value.param == param and e.value.message


def test_the_limits_are_accepted():
    assert by_name(plan(slide_height=141.5))["Drawer side"].width == 141.5
    assert by_name(plan(slide_length=512))["Drawer side"].length == 512


def hardware(**kw):
    return plan_hardware(**{**DEFAULTS, "screw_spacing": SPACING, **kw})


@pytest.mark.parametrize("thickness, length", [(6, 19), (9.5, 19), (12.7, 25), (15, 32), (18, 32), (19, 32), (19.1, 32), (25, 38), (25.4, 38),
                                               (30, 50), (38, 50), (45, 64)])
def test_the_pocket_screw_length_follows_the_thickness(thickness, length):
    assert pocket_screw_length(thickness) == length


@pytest.mark.parametrize("joint, count", [(100, 2), (141.5, 2), (150, 2), (151, 3), (294, 3), (300, 3), (450, 4), (512, 5)])
def test_screws_per_joint_at_most_one_spacing_apart_and_at_least_two(joint, count):
    assert per_joint(joint, 150) == count


def test_the_hardware_of_the_example():
    got = [(h.name, h.qty) for h in hardware()]
    assert got == [("Pocket screw, box", 20), ("Pocket screw, drawers", 16), ("Drawer pull", 2)]
    assert all(isinstance(h, Hardware) for h in hardware())
    box, drawers, pulls = hardware()
    assert "32 mm" in box.detail and "fine thread" in box.detail and "5 per joint" in box.detail and "4 joints" in box.detail
    assert "2 per corner" in drawers.detail and "4 corners" in drawers.detail and "32 mm" in drawers.detail
    assert "one per drawer" in pulls.detail


def test_a_tall_drawer_gets_more_screws_and_one_pull_per_drawer():
    one = {h.name: h for h in hardware(drawers=1)}
    assert one["Pocket screw, drawers"].qty == 4 * 3                       # side height 294: 3 per corner
    assert one["Drawer pull"].qty == 1
    assert {h.name: h.qty for h in hardware(drawers=3)}["Drawer pull"] == 3


def test_the_screw_follows_the_sheet_and_the_spacing():
    assert "25 mm" in hardware(thick=12.7)[0].detail
    assert hardware(screw_spacing=100)[0].qty == 4 * per_joint(512, 100)


def test_the_hardware_is_refused_like_the_pieces():
    with pytest.raises(DrawerError) as e:
        hardware(slide_height=200)
    assert e.value.param == "slide_height"
    with pytest.raises(DrawerError) as e:
        hardware(screw_spacing=0)
    assert e.value.param == "screw_spacing"


def test_csv():
    lines = pieces_to_csv(plan()).splitlines()
    assert lines[0] == "Piece,Material,Thickness,Quantity,Length,Width"
    assert lines[1] == "Box top and bottom,thick,18,2,756,512"
    assert lines[4] == "Drawer side,thick,18,4,500,141.5"
    assert len(lines) == 8
    assert isinstance(plan()[0], Piece)
    both = pieces_to_csv(plan(), hardware()).splitlines()
    assert both[:8] == lines and both[8] == ""
    assert both[9] == "Hardware,Detail,Quantity"
    rows = list(csv.reader(both))
    assert rows[10] == ["Pocket screw, box", "32 mm, fine thread (18 mm sheet); 5 per joint x 4 joints", "20"]
    assert rows[-1] == ["Drawer pull", "one per drawer", "2"]
