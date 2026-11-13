"""The data of a cutsheet (standard library only): labels, the sheets with their pieces and cuts, cut instructions,
pocket screw marks and the summary. The packing is core/cutting.py; the PDF is app/cutsheet_pdf.py."""
import math
from dataclasses import dataclass
from typing import Callable, Mapping

from core import catalogue, cutting
from core.cutting import Cut, Item, Placed, Sheet, Solution
from core.drawer_rules import Hardware, Piece, per_joint
from core.params import length_mm

MATERIALS = ("thick", "thin")
# the pieces that get pocket holes in the ends that are `width` long (the hardware rules): both short ends of the drawer
# fronts and backs, both long edges of the box sides
POCKET_PIECES = ("Drawer front and back", "Box side")


@dataclass(frozen=True)
class Label:
    label: str
    piece: Piece


@dataclass(frozen=True)
class PocketEdge:
    edge: str                    # "left" or "right" end of the piece drawn with its length across
    offsets: tuple               # mm from the start (top) of that edge, (i + 0.5) x edge length / n


def label_names(count: int) -> list:
    """A, B, ... Z, AA, AB, ..."""
    names = []
    for i in range(count):
        n, name = i, ""
        while True:
            name = chr(ord("A") + n % 26) + name
            n = n // 26 - 1
            if n < 0:
                break
        names.append(name)
    return names


def _g(x: float) -> str:
    return "%g" % round(x, 3)


def item_labels(label: Label) -> list:
    """The labels of the copies of a piece on the sheets: A1, A2 ... or just A for a single piece."""
    return [label.label] if label.piece.qty == 1 else ["%s%d" % (label.label, i + 1) for i in range(label.piece.qty)]


def _labels(pieces) -> list:
    return [Label(n, p) for n, p in zip(label_names(len(pieces)), pieces)]


def _items(labels, material) -> list:
    return [Item(name, l.piece.length, l.piece.width) for l in labels if l.piece.material == material for name in item_labels(l)]


@dataclass(frozen=True)
class SheetPlan:
    number: int                  # 1-based over all sheets, thick first
    material: str
    thickness: float
    length: float
    width: float
    placed: tuple
    cuts: tuple
    waste: float                 # mm2, offcuts and kerf

    @property
    def waste_percent(self) -> float:
        return 100.0 * self.waste / (self.length * self.width)

    def instructions(self) -> list:
        return [_instruction(self, c) for c in self.cuts]


def _instruction(sheet: SheetPlan, cut: Cut) -> str:
    r = cut.rect
    whole = r.x == 0 and r.y == 0 and r.w == sheet.length and r.h == sheet.width
    what = ("across the whole %s x %s sheet" % (_g(sheet.length), _g(sheet.width)) if whole else
            "across the %s x %s part that starts %s from the left and %s from the top" % (_g(r.w), _g(r.h), _g(r.x), _g(r.y)))
    distance = cut.at - (r.x if cut.vertical else r.y)
    return "Cut %d: %s, %s from the %s edge, kerf on the waste side" % (
        cut.number, what, _g(distance), "left" if cut.vertical else "top")


@dataclass(frozen=True)
class Cutsheet:
    labels: tuple
    sheets: tuple
    hardware: tuple
    params: Mapping
    kerf: float
    screw_spacing: float

    def label_of(self, name: str) -> Label:
        """The label record of 'A' or of one of its copies, 'A2'."""
        for l in self.labels:
            if name == l.label or name in item_labels(l):
                return l
        raise KeyError(name)

    def pocket_marks(self, name: str) -> list:
        piece = self.label_of(name).piece
        if piece.name not in POCKET_PIECES:
            return []
        n = per_joint(piece.width, self.screw_spacing)
        offsets = tuple(round((i + 0.5) * piece.width / n, 3) for i in range(n))
        return [PocketEdge("left", offsets), PocketEdge("right", offsets)]

    def summary(self) -> dict:
        counts = {}
        for s in self.sheets:
            counts[s.material] = counts.get(s.material, 0) + 1
        return {"sheets": counts, "total_sheets": len(self.sheets),
                "waste": [(s.number, s.material, s.waste_percent) for s in self.sheets]}


def build_cutsheet(pieces, hardware, params: Mapping, solutions: Mapping) -> Cutsheet:
    labels = tuple(_labels(pieces))
    sheets, number = [], 0
    for material in MATERIALS:
        if material not in solutions:
            continue
        length, width = catalogue.sheet_for(params, material)
        thickness = next(p.thickness for p in pieces if p.material == material)
        for layout in solutions[material].layouts:
            number += 1
            sheets.append(SheetPlan(number, material, thickness, length, width, layout.placed, layout.cuts, layout.waste))
    return Cutsheet(labels, tuple(sheets), tuple(hardware), dict(params), length_mm(params["kerf"]),
                    length_mm(params["screw_spacing"]))


def plan_cutsheet(p: Mapping, *, seconds: float = 15.0, iterations=None, workers=None, seed: int = 0, start=None,
                  on_progress: Callable | None = None, cancel: Callable | None = None) -> dict:
    """One search per material present, each with a share of the time. p are the normalised parameters of the part.
    on_progress(material, solution) is called with each better solution. Returns {material: Solution}."""
    pieces = catalogue.drawer_block_pieces(p)
    labels = _labels(pieces)
    kerf = length_mm(p["kerf"])
    materials = [m for m in MATERIALS if any(l.piece.material == m for l in labels)]
    result = {}
    for material in materials:
        sheet = Sheet(*catalogue.sheet_for(p, material))
        progress = (lambda sol, m=material: on_progress(m, sol)) if on_progress else None
        result[material] = cutting.optimize(
            _items(labels, material), sheet, kerf, seconds=seconds / len(materials), iterations=iterations, workers=workers,
            seed=seed, start=(start or {}).get(material), on_progress=progress, cancel=cancel)
    return result
