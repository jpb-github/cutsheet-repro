"""The rules of a block of drawers made of MDF: from the available space and a few parameters to the list of pieces to cut.

Standard library only. generators/DrawerBlocks/skills/drawer-blocks-generator/scripts/d02_rules.py is the EXACT copy of this
file (the generator runs in its own process and cannot import core): a test keeps them equal, change both together.
All dimensions in mm; the spec is docs/superpowers/specs/2026-11-13-drawer-blocks-design.md.

Construction: an outside box (two sides sandwiched between a top and a bottom, an overlay back at the rear behind them, the
facades in front of it), drawers (front and back sandwiched between the sides, the bottom nailed under, not recessed) with the
slides outside of them. THICK is the thick sheet (sides, top, bottom, drawer parts, facades), THIN the thin one (back, bottoms).
"""
import csv
import io
import math
from dataclasses import dataclass


class DrawerError(ValueError):
    """An impossible block; .param names the parameter to change, .message says why."""

    def __init__(self, param: str, message: str):
        super().__init__("%s: %s" % (param, message))
        self.param = param
        self.message = message


@dataclass(frozen=True)
class Piece:
    name: str
    material: str          # "thick" or "thin"
    qty: int
    length: float
    width: float
    thickness: float


@dataclass(frozen=True)
class Hardware:
    name: str
    qty: int
    detail: str


# Pocket screws (Kreg's chart): the length depends on the thickness of the sheet that is drilled, fine thread for MDF. (up to thickness mm, screw length mm)
POCKET_SCREWS = ((9.5, 19), (12.7, 25), (19.1, 32), (25.4, 38), (38.1, 50))
LONGEST_POCKET_SCREW = 64


def pocket_screw_length(thickness: float) -> int:
    """The length in mm of the pocket screw for a sheet of this thickness (3/8 in 19, 1/2 in 25, 3/4 in 32, 1 in 38, 1 1/2 in 50, more 64)."""
    return next((length for limit, length in POCKET_SCREWS if thickness <= limit), LONGEST_POCKET_SCREW)


def per_joint(joint_length: float, spacing: float) -> int:
    """Pocket screws along a joint: at most `spacing` mm apart, at least 2 (one near each end)."""
    return max(2, math.ceil(joint_length / spacing) + 1)


def _n(x: float) -> float:
    """Rounded to 0.001 mm and an integer when it is one (so 756.0 is 756)."""
    x = round(x, 3)
    return int(x) if x == int(x) else x


def geometry(*, width: float, height: float, depth: float, box_clearance: float, drawers: int, drawer_clearance: float,
                      thick: float, thin: float, slide_thickness: float, slide_length: float, slide_height: float,
                      slide_clearance: float) -> list[Piece]:
    """The validated sizes of the block that fits the available space width x height x depth (facades and box included).

    Raises DrawerError when a size would not be positive or the slides do not fit."""
    if drawers < 1:
        raise DrawerError("drawers", "there must be at least one drawer")
    if slide_height <= 0:
        raise DrawerError("slide_height", "the slide height must be above 0")
    box_w, box_h, box_d = width - box_clearance, height - box_clearance, depth - box_clearance
    panel_d = box_d - thick - thin                          # sides, top, bottom: the facade is in front, the back behind
    inner_h = box_h - 2 * thick                             # between the top and the bottom
    inner_w = box_w - 2 * thick
    if inner_h <= 0:
        raise DrawerError("thick", "two thick sheets leave no height in the box (%g mm)" % inner_h)
    if panel_d <= 0:
        raise DrawerError("thin", "the facade and the back leave no depth in the box (%g mm)" % panel_d)
    if inner_w <= 0:
        raise DrawerError("width", "the box is too narrow: no width left between the sides (%g mm)" % inner_w)
    drawer_h = (inner_h - drawer_clearance * (drawers + 1)) / drawers          # with its bottom
    side_h = drawer_h - thin                                                     # the bottom is nailed under the sides
    if side_h <= 0:
        raise DrawerError("drawers", "the drawers would have no height (%g mm of side): fewer drawers or a smaller clearance" % side_h)
    facade_h = (box_h - drawer_clearance * (drawers + 1)) / drawers
    drawer_w = box_w - 2 * thick - 2 * (slide_thickness + 2 * slide_clearance)  # outside width, between the slides
    front_w = drawer_w - 2 * thick                                               # sandwiched between the sides
    if front_w <= 0:
        raise DrawerError("slide_thickness", "the slides and the drawer sides leave no width for the drawer front (%g mm)" % front_w)
    if slide_length > panel_d:
        raise DrawerError("slide_length", "the slides (%g mm) are longer than the box depth (%g mm)" % (slide_length, panel_d))
    if slide_height > side_h:
        raise DrawerError("slide_height", "the slide height (%g mm) is more than the drawer side height (%g mm)" % (slide_height, _n(side_h)))
    return dict(box_w=box_w, box_h=box_h, panel_d=panel_d, inner_h=inner_h, side_h=side_h, facade_h=facade_h, drawer_w=drawer_w,
                front_w=front_w)


KEYS = ("width", "height", "depth", "box_clearance", "drawers", "drawer_clearance", "thick", "thin", "slide_thickness", "slide_length",
        "slide_height", "slide_clearance")


def plan_drawer_block(*, width: float, height: float, depth: float, box_clearance: float, drawers: int, drawer_clearance: float,
                      thick: float, thin: float, slide_thickness: float, slide_length: float, slide_height: float,
                      slide_clearance: float) -> list[Piece]:
    """The pieces to cut. Raises DrawerError like geometry."""
    g = geometry(**{k: v for k, v in locals().items() if k in KEYS})
    box_w, box_h, panel_d, inner_h, side_h, facade_h, drawer_w, front_w = (g[k] for k in (
        "box_w", "box_h", "panel_d", "inner_h", "side_h", "facade_h", "drawer_w", "front_w"))
    return [
        Piece("Box top and bottom", "thick", 2, _n(box_w), _n(panel_d), _n(thick)),
        Piece("Box side", "thick", 2, _n(inner_h), _n(panel_d), _n(thick)),
        Piece("Box back", "thin", 1, _n(box_w), _n(box_h), _n(thin)),
        Piece("Drawer side", "thick", 2 * drawers, _n(slide_length), _n(side_h), _n(thick)),
        Piece("Drawer front and back", "thick", 2 * drawers, _n(front_w), _n(side_h), _n(thick)),
        Piece("Drawer bottom", "thin", drawers, _n(drawer_w), _n(slide_length), _n(thin)),
        Piece("Facade", "thick", drawers, _n(box_w), _n(facade_h), _n(thick)),
    ]



def plan_hardware(*, screw_spacing: float, **kw) -> list[Hardware]:
    """The pocket screws and the drawer pulls (the same keyword arguments as plan_drawer_block, plus the largest spacing of the screws).

    Pocket holes are drilled in the ends of the box sides (to the top and the bottom: 4 joints along the depth of the box) and of the
    drawer fronts and backs (to the sides: 4 corners along the height of the drawer side), in the thick sheet; the thin back and
    bottoms are nailed. Every joint gets per_joint() screws. One pull per drawer."""
    if screw_spacing <= 0:
        raise DrawerError("screw_spacing", "the screw spacing must be above 0")
    g = geometry(**kw)
    drawers, thick = kw["drawers"], kw["thick"]
    length = pocket_screw_length(thick)
    spec = "%d mm, fine thread (%g mm sheet)" % (length, thick)
    box_n, corner_n = per_joint(g["panel_d"], screw_spacing), per_joint(g["side_h"], screw_spacing)
    return [
        Hardware("Pocket screw, box", 4 * box_n, "%s; %d per joint x 4 joints" % (spec, box_n)),
        Hardware("Pocket screw, drawers", 4 * corner_n * drawers, "%s; %d per corner x 4 corners x %d %s" % (
            spec, corner_n, drawers, "drawer" if drawers == 1 else "drawers")),
        Hardware("Drawer pull", drawers, "one per drawer"),
    ]


def pieces_to_csv(pieces: list[Piece], hardware: list[Hardware] | None = None) -> str:
    """The list as CSV text: a header and one line per piece, then (when given) an empty line, a header and one line per hardware item."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator=chr(10))
    w.writerow(("Piece", "Material", "Thickness", "Quantity", "Length", "Width"))
    for p in pieces:
        w.writerow((p.name, p.material, "%g" % p.thickness, p.qty, "%g" % p.length, "%g" % p.width))
    if hardware:
        w.writerow(())
        w.writerow(("Hardware", "Detail", "Quantity"))
        for h in hardware:
            w.writerow((h.name, h.detail, h.qty))
    return out.getvalue()
