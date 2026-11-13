"""Part catalogue: every cutsheet with its parameters, validation, output names and generator command line.

No generator is run here and nothing outside the standard library is imported: a Part only turns validated parameters into
an Invocation (script path relative to generators/, argument list, output names). Running is the runner's job (core/runner.py).
New parts are added to PARTS below; the tab says where the GUI shows the part.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Mapping

from core import drawer_rules, drawer_view
from core.drawer_rules import DrawerError, Hardware, Piece
from core.params import Param, ParamError, fmt_mm, length_mm, normalise_values


@dataclass(frozen=True)
class Invocation:
    script: str                  # relative to generators/, forward slashes
    args: tuple[str, ...]        # everything after the script path; output paths absolute under out_dir
    outputs: tuple[str, ...]     # names relative to out_dir; the first is the main result (may be a folder)


@dataclass(frozen=True)
class Part:
    key: str
    label: str
    tab: Literal["drawer_blocks"]
    group: str
    params: tuple[Param, ...]
    script: str | None
    seed: str | None = None      # a fixed part: the name of a bundled file (seed/) that is served as it is
    _seed: Callable[[Mapping], str | None] | None = field(default=None, repr=False, compare=False)   # same, chosen by the parameters
    _names: Callable[[Mapping], tuple[str, ...]] = field(default=lambda p: (), repr=False, compare=False)
    _args: Callable[[Mapping, Path], tuple[str, ...]] = field(default=lambda p, o: (), repr=False, compare=False)
    _check: Callable[[Mapping], None] | None = field(default=None, repr=False, compare=False)
    _canon: Callable[[dict], dict] | None = field(default=None, repr=False, compare=False)   # makes unused values canonical

    def normalise(self, raw: Mapping[str, object] | None = None) -> dict[str, object]:
        params = normalise_values(self.params, raw or {})
        if self._canon:
            params = self._canon(params)
        if self._check:
            self._check(params)
        return params

    def seed_for(self, params: Mapping) -> str | None:
        """The bundled file that is this part for these (normalised) parameters, None when the part is generated."""
        return self._seed(params) if self._seed else self.seed

    def output_names(self, params: Mapping) -> tuple[str, ...]:
        name = self.seed_for(params)
        return (name,) if name else self._names(params)

    def invocation(self, params: Mapping, out_dir: Path) -> Invocation:
        if self.script is None:
            raise ValueError("%s is a fixed part, nothing to run" % self.key)
        return Invocation(self.script, self._args(params, Path(out_dir)), self.output_names(params))


def _out(out_dir: Path, name: str) -> str:
    return str(out_dir / name)


# the parameters that are lengths (canonical "NNNmm" texts); the rules and the command line use the same names (_ become -)
DRAWER_LENGTHS = ("width", "height", "depth", "box_clearance", "drawer_clearance", "thick", "thin", "slide_thickness", "slide_length",
                  "slide_height", "slide_clearance", "screw_spacing")


def drawer_block_pieces(p: Mapping) -> list[Piece]:
    """The pieces of the (normalised) parameters of the drawer_blocks part; raises ParamError (the rules' DrawerError, same parameter)."""
    try:
        return drawer_rules.plan_drawer_block(drawers=p["drawers"], **_rule_args(p))
    except DrawerError as e:
        raise ParamError(e.param, e.message)


def drawer_block_hardware(p: Mapping) -> list[Hardware]:
    """The pocket screws and the drawer pulls of the (normalised) parameters; raises ParamError like drawer_block_pieces."""
    try:
        return drawer_rules.plan_hardware(drawers=p["drawers"], screw_spacing=length_mm(p["screw_spacing"]), **_rule_args(p))
    except DrawerError as e:
        raise ParamError(e.param, e.message)


def drawer_block_boxes(p: Mapping) -> list[drawer_view.Box]:
    """Every part of the (normalised) block placed in space, for the view; raises ParamError like drawer_block_pieces."""
    try:
        return drawer_view.block_boxes(drawers=p["drawers"], **_rule_args(p))
    except DrawerError as e:
        raise ParamError(e.param, e.message)


def _rule_args(p: Mapping) -> dict:
    return {k: length_mm(p[k]) for k in DRAWER_LENGTHS if k != "screw_spacing"}


def _drawer_blocks() -> Part:
    def length(name, label, default, lo, hi, help, advanced=False):
        return Param(name, label, "length", default, min=lo, max=hi, help=help, advanced=advanced)
    params = (length("width", "Available width", "760mm", 50, 3000, "the total width the block must fit in, facades included"),
              length("height", "Available height", "350mm", 50, 3000, "the total height the block must fit in, facades included"),
              length("depth", "Available depth", "540mm", 50, 1500, "the total depth the block must fit in, facade and back included"),
              length("box_clearance", "Box clearance", "4mm", 0, 50, "taken once from each of the three dimensions (about half on each side)"),
              Param("drawers", "Number of drawers", "int", 2, min=1, max=12, help="drawers one above the other"),
              length("drawer_clearance", "Drawer clearance", "5mm", 0, 50, "the gap above and below every drawer and facade"),
              length("thick", "Thick sheet", "18mm", 3, 50, "MDF of the box, the drawer sides, fronts and backs, and the facades"),
              length("thin", "Thin sheet", "6mm", 2, 30, "MDF of the box back and the drawer bottoms"),
              length("slide_thickness", "Slide thickness", "12mm", 0, 50, "the slides are outside the drawer, between it and the box side"),
              length("slide_length", "Slide length", "500mm", 50, 1500, "also the depth of the drawers"),
              length("slide_height", "Slide height", "35mm", 1, 200, "must not exceed the height of the drawer sides"),
              length("slide_clearance", "Slide clearance", "0.5mm", 0, 5, "on each side of each slide (box to slide, slide to drawer)"),
              length("screw_spacing", "Pocket screw spacing", "150mm", 50, 400, "the largest distance between two pocket screws along a joint (at least 2 per joint)"))

    def names(p):
        return ("Drawer Blocks - %d drawers %sx%sx%s.csv" % (p["drawers"], fmt_mm(length_mm(p["width"])), fmt_mm(length_mm(p["height"])),
                                                              fmt_mm(length_mm(p["depth"]))),)

    def args(p, o):
        opts = []
        for k in DRAWER_LENGTHS:
            opts += ["--" + k.replace("_", "-"), fmt_mm(length_mm(p[k]))]
        return ("--drawers", str(p["drawers"]), *opts, "--out", _out(o, names(p)[0]))
    def check(p):
        drawer_block_pieces(p)
        drawer_block_hardware(p)

    return Part("drawer_blocks", "Drawer Blocks", "drawer_blocks", "Cutsheet", params,
                "DrawerBlocks/skills/drawer-blocks-generator/scripts/build_cutlist.py", _names=names, _args=args, _check=check)


PARTS: dict[str, Part] = {p.key: p for p in (_drawer_blocks(),)}


def get_part(key: str) -> Part:
    try:
        return PARTS[key]
    except KeyError:
        raise KeyError("unknown part %r (known: %s)" % (key, ", ".join(PARTS) or "none yet"))
