import math

import pytest

from core.drawer_view import Box, block_boxes, exterior, project_faces

DEFAULTS = dict(width=760, height=350, depth=540, box_clearance=4, drawers=2, drawer_clearance=5, thick=18, thin=6,
                slide_thickness=12, slide_length=500, slide_height=35, slide_clearance=0.5)


def boxes(**kw):
    return block_boxes(**{**DEFAULTS, **kw})


def overlap(a: Box, b: Box) -> float:
    dx = min(a.x + a.dx, b.x + b.dx) - max(a.x, b.x)
    dy = min(a.y + a.dy, b.y + b.dy) - max(a.y, b.y)
    dz = min(a.z + a.dz, b.z + b.dz) - max(a.z, b.z)
    return dx * dy * dz if min(dx, dy, dz) > 1e-9 else 0.0


def test_the_example_has_21_parts_and_the_size_of_the_box():
    b = boxes()
    kinds = [x.kind for x in b]
    assert len(b) == 21 + 2 and kinds.count("facade") == 2 and kinds.count("pull") == 2 and kinds.count("slide") == 4
    assert (min(x.x for x in b), max(x.x + x.dx for x in b)) == (0, 756)
    assert (min(x.z for x in b), max(x.z + x.dz for x in b)) == (0, 346)
    assert max(x.y + x.dy for x in b) == 536 and min(x.y for x in b) == -14        # the pulls stand out in front of the facades


def test_no_two_parts_overlap():
    b = [x for x in boxes() if x.kind != "pull"]
    assert [(p.name, q.name) for i, p in enumerate(b) for q in b[i + 1:] if overlap(p, q) > 0] == []


def test_drawers_match_the_cut_list():
    b = {x.name: x for x in boxes()}
    assert (b["Drawer 1 bottom"].dx, b["Drawer 1 bottom"].dy, b["Drawer 1 bottom"].dz) == (694, 500, 6)
    assert (b["Drawer 2 front"].dx, b["Drawer 2 front"].dz) == (658, 141.5)
    assert (b["Facade 1"].dx, b["Facade 1"].dz, b["Facade 1"].z) == (756, 165.5, 5)
    assert b["Drawer 1 slide left"].x == 18.5 and b["Drawer 1 slide left"].dz == 35


def test_one_drawer_and_invalid_requests():
    assert [x.kind for x in boxes(drawers=1)].count("facade") == 1
    with pytest.raises(ValueError):
        boxes(slide_height=500)


def test_projection_hides_the_back_and_each_box_shows_at_most_three_faces():
    faces = project_faces(boxes())
    assert faces and all(len(f.points) == 4 for f in faces)
    per_box = {}
    for f in faces:
        per_box[f.name] = per_box.get(f.name, 0) + 1
    assert max(per_box.values()) <= 3
    xs = [p[0] for f in faces for p in f.points]
    ys = [p[1] for f in faces for p in f.points]
    assert all(math.isfinite(v) for v in xs + ys) and max(xs) > min(xs) and max(ys) > min(ys)


def test_a_box_is_painted_after_the_boxes_behind_it():
    order = [(f.name, f.side) for f in project_faces(exterior(boxes()))]
    pos = {key: i for i, key in enumerate(order)}
    # the front edge of the box side is behind the facades that cover it: it must be painted first (it hid the strips of the facades)
    assert pos[("Box side right", "front")] < pos[("Facade 1", "right")] < pos[("Facade 1", "front")] or pos[("Box side right", "front")] < pos[("Facade 1", "right")]
    assert pos[("Box side right", "front")] < pos[("Facade 2", "right")]
    assert pos[("Box side right", "right")] < pos[("Facade 1", "right")]
    assert pos[("Box top", "right")] < pos[("Facade 2", "right")] and pos[("Box back", "front")] < pos[("Box side left", "front")]
    assert pos[("Facade 1", "front")] < pos[("Pull 1", "front")] and pos[("Facade 2", "front")] < pos[("Pull 2", "front")]


def test_the_drawers_inside_are_painted_before_the_facades_that_hide_them():
    order = [(f.name, f.side) for f in project_faces(boxes())]
    pos = {key: i for i, key in enumerate(order)}
    assert pos[("Drawer 1 front", "front")] < pos[("Facade 1", "front")] and pos[("Drawer 2 slide right", "right")] < pos[("Box side right", "right")]


def test_the_view_is_from_the_front_right_and_above():
    faces = project_faces(boxes())
    visible = {(f.name, f.side) for f in faces}
    assert {("Facade 1", "front"), ("Box top", "top"), ("Box top", "right"), ("Box side right", "right")} <= visible
    assert not any(f.side in ("back", "left", "bottom") for f in faces)


def test_the_closed_block_shows_only_its_exterior():
    outside = exterior(boxes())
    assert sorted(x.kind for x in outside) == ["facade", "facade", "pull", "pull", "thick", "thick", "thick", "thick", "thin"]
    assert not any(x.name.startswith(("Drawer", "Pull 3")) for x in outside)
    faces = project_faces(outside)
    assert {"Facade 1", "Facade 2", "Pull 1", "Pull 2", "Box top", "Box side right"} <= {f.name for f in faces}    # hidden panels are drawn first and covered
    assert not any(f.name.startswith("Drawer") for f in faces)
