"""The rules of a block of drawers made of MDF: from the available space and a few parameters to the list of pieces to cut.

Standard library only. generators/DrawerBlocks/skills/drawer-blocks-generator/scripts/d02_rules.py is the EXACT copy of this
file (the generator runs in its own process and cannot import core): a test keeps them equal, change both together.
All dimensions in mm; the spec is docs/superpowers/specs/2026-11-13-drawer-blocks-design.md.

Construction: an outside box (two sides sandwiched between a top and a bottom, an overlay back at the rear behind them, the
facades in front of it), drawers (front and back sandwiched between the sides, the bottom nailed under, not recessed) with the
slides outside of them. THICK is the thick sheet (sides, top, bottom, drawer parts, facades), THIN the thin one (back, bottoms).
"""
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


def _n(x: float) -> float:
    """Rounded to 0.001 mm and an integer when it is one (so 756.0 is 756)."""
    x = round(x, 3)
    return int(x) if x == int(x) else x


def plan_drawer_block(*, width: float, height: float, depth: float, box_clearance: float, drawers: int, drawer_clearance: float,
                      thick: float, thin: float, slide_thickness: float, slide_length: float, slide_height: float,
                      slide_clearance: float) -> list[Piece]:
    """The pieces of the block that fits the available space width x height x depth (facades and box included).

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
    return [
        Piece("Box top and bottom", "thick", 2, _n(box_w), _n(panel_d), _n(thick)),
        Piece("Box side", "thick", 2, _n(inner_h), _n(panel_d), _n(thick)),
        Piece("Box back", "thin", 1, _n(box_w), _n(box_h), _n(thin)),
        Piece("Drawer side", "thick", 2 * drawers, _n(slide_length), _n(side_h), _n(thick)),
        Piece("Drawer front and back", "thick", 2 * drawers, _n(front_w), _n(side_h), _n(thick)),
        Piece("Drawer bottom", "thin", drawers, _n(drawer_w), _n(slide_length), _n(thin)),
        Piece("Facade", "thick", drawers, _n(box_w), _n(facade_h), _n(thick)),
    ]


def pieces_to_csv(pieces: list[Piece]) -> str:
    """The list as CSV text (header, one line per piece), lines ended by \\n."""
    lines = ["Piece,Material,Thickness,Quantity,Length,Width"]
    lines += ["%s,%s,%g,%d,%g,%g" % (p.name, p.material, p.thickness, p.qty, p.length, p.width) for p in pieces]
    return "\n".join(lines) + "\n"
