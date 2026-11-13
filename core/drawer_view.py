"""The block of drawers as boxes in space and their perspective view: standard library only, no drawing here (app/block_view.py draws).

block_boxes gives every part as an axis-aligned box in mm (x = width, y = depth with 0 at the front of the facades, z = up), the
same sizes as the cut list (core/drawer_rules.py). project_faces looks at them from the front, the right and above, with a real
perspective, and returns the visible faces as 2D polygons, y up, in arbitrary units, in the order to paint them (painter's algorithm:
each box after the boxes behind it, found from the planes that separate the boxes; sorting faces by their middle fails for a large
panel beside the small parts it touches, e.g. the front edge of the box side drawn over the side of a facade).
"""
import math
from dataclasses import dataclass

from core import drawer_rules

PULL_W, PULL_H, PULL_OUT = 100.0, 14.0, 14.0         # the pull is only drawn (a bar on the facade); its size is not part of the cut list
YAW, PITCH, DISTANCE = math.radians(32), math.radians(22), 2.4      # camera: right of the front, above, distance in diagonals
LIGHT = (-0.35, -0.55, 0.75)


@dataclass(frozen=True)
class Box:
    name: str
    kind: str          # "thick", "thin", "facade", "slide" or "pull"
    x: float
    y: float
    z: float
    dx: float
    dy: float
    dz: float


@dataclass(frozen=True)
class Face:
    name: str
    kind: str
    side: str          # "front", "back", "left", "right", "top" or "bottom"
    points: tuple      # four (x, y) points, y up
    distance: float    # from the camera to the middle of the face (information: the list is already in painting order)
    shade: float       # 0.5 (dark) to 1.0 (lit)


def block_boxes(*, width: float, height: float, depth: float, box_clearance: float, drawers: int, drawer_clearance: float,
                thick: float, thin: float, slide_thickness: float, slide_length: float, slide_height: float,
                slide_clearance: float) -> list[Box]:
    """Every part of the block, placed. Raises DrawerError (a ValueError) when the block is impossible, like plan_drawer_block."""
    args = dict(width=width, height=height, depth=depth, box_clearance=box_clearance, drawers=drawers, drawer_clearance=drawer_clearance,
                thick=thick, thin=thin, slide_thickness=slide_thickness, slide_length=slide_length, slide_height=slide_height,
                slide_clearance=slide_clearance)
    g = drawer_rules.geometry(**args)
    box_w, box_h, panel_d = g["box_w"], g["box_h"], g["panel_d"]
    side_h, facade_h, drawer_w, front_w = g["side_h"], g["facade_h"], g["drawer_w"], g["front_w"]
    drawer_h = side_h + thin
    y0 = thick                                                  # the facades are in front of the box
    out = [Box("Box bottom", "thick", 0, y0, 0, box_w, panel_d, thick),
           Box("Box top", "thick", 0, y0, box_h - thick, box_w, panel_d, thick),
           Box("Box side left", "thick", 0, y0, thick, thick, panel_d, box_h - 2 * thick),
           Box("Box side right", "thick", box_w - thick, y0, thick, thick, panel_d, box_h - 2 * thick),
           Box("Box back", "thin", 0, y0 + panel_d, 0, box_w, thin, box_h)]
    x0 = thick + slide_thickness + 2 * slide_clearance
    for i in range(drawers):
        zf = drawer_clearance + i * (facade_h + drawer_clearance)
        zd = thick + drawer_clearance + i * (drawer_h + drawer_clearance)
        n = "Drawer %d " % (i + 1)
        zs = zd + thin + (side_h - slide_height) / 2
        out += [Box("Facade %d" % (i + 1), "facade", 0, 0, zf, box_w, thick, facade_h),
                Box("Pull %d" % (i + 1), "pull", (box_w - PULL_W) / 2, -PULL_OUT, zf + (facade_h - PULL_H) / 2, PULL_W, PULL_OUT, PULL_H),
                Box(n + "bottom", "thin", x0, y0, zd, drawer_w, slide_length, thin),
                Box(n + "side left", "thick", x0, y0, zd + thin, thick, slide_length, side_h),
                Box(n + "side right", "thick", x0 + drawer_w - thick, y0, zd + thin, thick, slide_length, side_h),
                Box(n + "front", "thick", x0 + thick, y0, zd + thin, front_w, thick, side_h),
                Box(n + "back", "thick", x0 + thick, y0 + slide_length - thick, zd + thin, front_w, thick, side_h),
                Box(n + "slide left", "slide", thick + slide_clearance, y0, zs, slide_thickness, slide_length, slide_height),
                Box(n + "slide right", "slide", box_w - thick - slide_thickness - slide_clearance, y0, zs, slide_thickness, slide_length,
                    slide_height)]
    return out


def exterior(boxes: list[Box]) -> list[Box]:
    """What is seen of the closed block: the box, the facades and the pulls (the drawers and slides are hidden inside)."""
    return [b for b in boxes if b.kind in ("facade", "pull") or b.name.startswith("Box ")]


# the six faces of a box: side name, outward normal, the four corners as (0/1 on x, y, z)
_FACES = (("front", (0, -1, 0), ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),
          ("back", (0, 1, 0), ((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1))),
          ("left", (-1, 0, 0), ((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1))),
          ("right", (1, 0, 0), ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1))),
          ("bottom", (0, 0, -1), ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))),
          ("top", (0, 0, 1), ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))))


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def _paint_order(boxes: list[Box], eye) -> list[Box]:
    """The boxes from the farthest to the nearest: A is painted before B when a plane separates them with the eye on B's side."""
    low = [(b.x, b.y, b.z) for b in boxes]
    high = [(b.x + b.dx, b.y + b.dy, b.z + b.dz) for b in boxes]
    behind = [set() for _ in boxes]                         # behind[j]: the boxes that must be painted before box j
    for i in range(len(boxes)):
        for j in range(len(boxes)):
            if i == j:
                continue
            verdicts = set()                                # one per plane that separates the two boxes: who is nearer
            for axis in range(3):
                if high[i][axis] <= low[j][axis] + 1e-9:                    # i below j along this axis
                    verdicts.add("j" if eye[axis] >= low[j][axis] else "i" if eye[axis] <= high[i][axis] else "-")
                elif high[j][axis] <= low[i][axis] + 1e-9:                  # i above j
                    verdicts.add("j" if eye[axis] <= high[j][axis] else "i" if eye[axis] >= low[i][axis] else "-")
            if verdicts - {"-"} == {"j"}:                           # planes that disagree mean that neither box can hide the other
                behind[j].add(i)
    far = lambda k: -math.dist([(low[k][a] + high[k][a]) / 2 for a in range(3)], eye)       # farthest first when nothing decides
    order, done = [], set()
    while len(order) < len(boxes):
        ready = [k for k in range(len(boxes)) if k not in done and behind[k] <= done]
        pool = ready or [k for k in range(len(boxes)) if k not in done]                    # a cycle (not expected): the farthest goes
        k = min(pool, key=far)
        order.append(k)
        done.add(k)
    return [boxes[k] for k in order]


def project_faces(boxes: list[Box]) -> list[Face]:
    """The faces that look at the camera, in the order to paint them (2D points, y up)."""
    lo = [min(getattr(b, a) for b in boxes) for a in "xyz"]
    hi = [max(getattr(b, a) + getattr(b, d) for b in boxes) for a, d in zip("xyz", ("dx", "dy", "dz"))]
    centre = [(a + b) / 2 for a, b in zip(lo, hi)]
    diagonal = math.dist(lo, hi)
    eye = (centre[0] + DISTANCE * diagonal * math.sin(YAW) * math.cos(PITCH),
           centre[1] - DISTANCE * diagonal * math.cos(YAW) * math.cos(PITCH),
           centre[2] + DISTANCE * diagonal * math.sin(PITCH))
    forward = _unit(_sub(centre, eye))
    right = _unit(_cross(forward, (0, 0, 1)))
    up = _cross(right, forward)
    light = _unit(LIGHT)
    faces = []
    for b in _paint_order(boxes, eye):
        size = (b.dx, b.dy, b.dz)
        origin = (b.x, b.y, b.z)
        for side, normal, corners in _FACES:
            points3 = [tuple(origin[i] + c[i] * size[i] for i in range(3)) for c in corners]
            middle = tuple(sum(p[i] for p in points3) / 4 for i in range(3))
            if _dot(_sub(middle, eye), normal) >= 0:         # looks away from the camera
                continue
            points = []
            for p in points3:
                v = _sub(p, eye)
                depth = _dot(v, forward)
                points.append((_dot(v, right) / depth, _dot(v, up) / depth))
            shade = 0.5 + 0.5 * max(0.0, _dot(normal, light))
            faces.append(Face(b.name, b.kind, side, tuple(points), math.dist(middle, eye), shade))
    return faces
