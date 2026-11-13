import pytest

from core.drawer_rules import DrawerError, Piece, pieces_to_csv, plan_drawer_block

DEFAULTS = dict(width=760, height=350, depth=540, box_clearance=4, drawers=2, drawer_clearance=5, thick=18, thin=6,
                slide_thickness=12, slide_length=500, slide_height=35, slide_clearance=0.5)


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


def test_csv():
    lines = pieces_to_csv(plan()).splitlines()
    assert lines[0] == "Piece,Material,Thickness,Quantity,Length,Width"
    assert lines[1] == "Box top and bottom,thick,18,2,756,512"
    assert lines[4] == "Drawer side,thick,18,4,500,141.5"
    assert len(lines) == 8
    assert isinstance(plan()[0], Piece)
