"""Guillotine packing of rectangles on sheets (standard library only).

One deterministic run: `pack(items, sheet, kerf, variant)`. Every cut crosses the whole rectangle it divides, so
the cuts form a tree; their order is the depth in the tree, then left to right, top to bottom. x runs along the
sheet length, y along its width. A piece is `length` along x unless it is rotated.
"""
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

EPS = 1e-6

SELECTS = ("short", "long", "area", "worst_area")
SPLITS = ("short", "long", "min_area", "max_area")
ORDERS = ("area", "long", "shuffle")


class CutError(ValueError):
    """A piece that fits no sheet."""


@dataclass(frozen=True)
class Item:
    label: str
    length: float
    width: float


@dataclass(frozen=True)
class Sheet:
    length: float
    width: float


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Placed:
    label: str
    x: float
    y: float
    w: float
    h: float
    rotated: bool


@dataclass(frozen=True)
class Cut:
    number: int
    stage: int
    vertical: bool      # True: the line is x = at (runs along y); False: y = at
    at: float           # absolute position of the line, on the edge of the piece (the blade is on the waste side)
    rect: Rect          # the rectangle this cut divides, across its whole width or height


@dataclass(frozen=True)
class SheetLayout:
    placed: tuple
    cuts: tuple
    waste: float
    largest_offcut: float


@dataclass(frozen=True)
class Variant:
    select: str
    split: str
    order: str
    seed: int


@dataclass
class _Free:
    rect: Rect
    stage: int


def _ordered(items, variant):
    items = list(items)
    if variant.order == "area":
        items.sort(key=lambda i: (-i.length * i.width, -max(i.length, i.width), i.label))
    elif variant.order == "long":
        items.sort(key=lambda i: (-max(i.length, i.width), -min(i.length, i.width), i.label))
    elif variant.order == "shuffle":
        items.sort(key=lambda i: (-i.length * i.width, i.label))
        random.Random(variant.seed).shuffle(items)
    else:
        raise ValueError("unknown order %r" % variant.order)
    return items


def _fit_score(select, rect, w, h):
    lw, lh = rect.w - w, rect.h - h
    if select == "short":
        return (min(lw, lh), max(lw, lh))
    if select == "long":
        return (max(lw, lh), min(lw, lh))
    if select == "area":
        return (rect.w * rect.h - w * h, 0)
    if select == "worst_area":
        return (-(rect.w * rect.h - w * h), 0)
    raise ValueError("unknown select %r" % select)


def _best_spot(frees, item, select):
    """(score, free index, rotated) of the best free rectangle for the item, or None."""
    best = None
    for index, free in enumerate(frees):
        for rotated in (False, True):
            w, h = (item.width, item.length) if rotated else (item.length, item.width)
            if rotated and abs(w - h) < EPS:
                continue
            if w > free.rect.w + EPS or h > free.rect.h + EPS:
                continue
            key = (_fit_score(select, free.rect, w, h), index, rotated)
            if best is None or key < best:
                best = key
    return best


def _horizontal_first(split, rect, w, h):
    """True: the first cut is horizontal across the whole width (the strip holds the piece), else vertical."""
    lw, lh = rect.w - w, rect.h - h
    if split == "short":
        return lw <= lh
    if split == "long":
        return lw > lh
    if split == "min_area":
        return w * lh > lw * h
    if split == "max_area":
        return not (w * lh > lw * h)
    raise ValueError("unknown split %r" % split)


def _place(free, w, h, kerf, split):
    """Place a w x h piece in the corner of the free rectangle: (new free rectangles, cuts as (stage, vertical, at, rect))."""
    r = free.rect
    new, cuts = [], []
    if _horizontal_first(split, r, w, h):
        stage = free.stage
        strip = r
        if r.h - h > EPS:                          # first cut: across the whole width, below the piece
            stage += 1
            cuts.append((stage, False, r.y + h, r))
            strip = Rect(r.x, r.y, r.w, h)
            if r.h - h - kerf > EPS:
                new.append(_Free(Rect(r.x, r.y + h + kerf, r.w, r.h - h - kerf), free.stage + 1))
        if r.w - w > EPS:                          # second cut: across the strip, right of the piece
            cuts.append((stage + 1, True, r.x + w, strip))
            if r.w - w - kerf > EPS:
                new.append(_Free(Rect(r.x + w + kerf, r.y, r.w - w - kerf, h), stage + 1))
    else:
        stage = free.stage
        strip = r
        if r.w - w > EPS:                          # first cut: across the whole height, right of the piece
            stage += 1
            cuts.append((stage, True, r.x + w, r))
            strip = Rect(r.x, r.y, w, r.h)
            if r.w - w - kerf > EPS:
                new.append(_Free(Rect(r.x + w + kerf, r.y, r.w - w - kerf, r.h), free.stage + 1))
        if r.h - h > EPS:                          # second cut: across the strip, below the piece
            cuts.append((stage + 1, False, r.y + h, strip))
            if r.h - h - kerf > EPS:
                new.append(_Free(Rect(r.x, r.y + h + kerf, w, r.h - h - kerf), stage + 1))
    return new, cuts


def pack(items, sheet, kerf, variant) -> list:
    """One deterministic run. A new sheet is opened when nothing fits; CutError when an item fits no sheet."""
    states = []                                    # per sheet: [frees, placed, cuts]
    for item in _ordered(items, variant):
        fits_empty = any(w <= sheet.length + EPS and h <= sheet.width + EPS
                         for w, h in ((item.length, item.width), (item.width, item.length)))
        if not fits_empty:
            raise CutError("%s (%g x %g) does not fit a %g x %g sheet" %
                           (item.label, item.length, item.width, sheet.length, sheet.width))
        spot = None
        for state in states:
            spot = _best_spot(state[0], item, variant.select)
            if spot:
                break
        if spot is None:
            state = [[_Free(Rect(0, 0, sheet.length, sheet.width), 0)], [], []]
            states.append(state)
            spot = _best_spot(state[0], item, variant.select)
        _score, index, rotated = spot
        frees, placed, cuts = state
        free = frees.pop(index)
        w, h = (item.width, item.length) if rotated else (item.length, item.width)
        placed.append(Placed(item.label, free.rect.x, free.rect.y, w, h, rotated))
        new, new_cuts = _place(free, w, h, kerf, variant.split)
        frees.extend(new)
        cuts.extend(new_cuts)
    return [_layout(sheet, *state) for state in states]


def _layout(sheet, frees, placed, cuts):
    cuts = sorted(cuts, key=lambda c: (c[0], c[3].x, c[3].y, c[1], c[2]))
    numbered = tuple(Cut(i + 1, stage, vertical, at, rect) for i, (stage, vertical, at, rect) in enumerate(cuts))
    waste = sheet.length * sheet.width - sum(p.w * p.h for p in placed)
    largest = max((f.rect.w * f.rect.h for f in frees), default=0)
    return SheetLayout(tuple(placed), numbered, waste, largest)


def check_layout(layouts, items, sheet, kerf) -> list:
    """The problems of a layout (empty when it is sound): outside the sheet, overlap, kerf, a missing or doubled
    piece, a cut that is not edge to edge."""
    problems = []
    wanted = {i.label: i for i in items}
    seen = {}
    for number, layout in enumerate(layouts, 1):
        where = "sheet %d" % number
        for p in layout.placed:
            seen[p.label] = seen.get(p.label, 0) + 1
            item = wanted.get(p.label)
            if item is None:
                problems.append("%s: %s is not a requested piece" % (where, p.label))
            elif sorted((p.w, p.h)) != sorted((item.length, item.width)):
                problems.append("%s: %s has the wrong size" % (where, p.label))
            if p.x < -EPS or p.y < -EPS or p.x + p.w > sheet.length + EPS or p.y + p.h > sheet.width + EPS:
                problems.append("%s: %s is outside the sheet" % (where, p.label))
        for a, b in ((a, b) for k, a in enumerate(layout.placed) for b in layout.placed[k + 1:]):
            gap_x = max(a.x - (b.x + b.w), b.x - (a.x + a.w))
            gap_y = max(a.y - (b.y + b.h), b.y - (a.y + a.h))
            if gap_x < -EPS and gap_y < -EPS:
                problems.append("%s: %s and %s overlap" % (where, a.label, b.label))
            elif (gap_x < kerf - EPS and gap_y < -EPS) or (gap_y < kerf - EPS and gap_x < -EPS):
                problems.append("%s: %s and %s are closer than the kerf" % (where, a.label, b.label))
        for c in layout.cuts:
            r = c.rect
            inside = (r.x >= -EPS and r.y >= -EPS and r.x + r.w <= sheet.length + EPS and r.y + r.h <= sheet.width + EPS)
            lo, hi = (r.x, r.x + r.w) if c.vertical else (r.y, r.y + r.h)
            if not inside or not (lo - EPS <= c.at <= hi + EPS):
                problems.append("%s: cut %d is outside its rectangle" % (where, c.number))
                continue
            for p in layout.placed:
                px, py, pw, ph = p.x, p.y, p.w, p.h
                across = (px < c.at - EPS < px + pw - 2 * EPS) if c.vertical else (py < c.at - EPS < py + ph - 2 * EPS)
                touches = (py < r.y + r.h - EPS and py + ph > r.y + EPS) if c.vertical else (
                    px < r.x + r.w - EPS and px + pw > r.x + EPS)
                if across and touches:
                    problems.append("%s: cut %d crosses piece %s" % (where, c.number, p.label))
    for label in wanted:
        count = seen.get(label, 0)
        if count == 0:
            problems.append("%s is missing" % label)
        elif count > 1:
            problems.append("%s is placed twice" % label)
    return problems


# ---------------------------------------------------------------- search

BATCH = 16


@dataclass(frozen=True)
class Solution:
    layouts: tuple
    score: tuple


def score(layouts) -> tuple:
    """Smaller is better: sheets, wasted area, cuts, minus the largest offcut."""
    return (len(layouts), sum(l.waste for l in layouts), sum(len(l.cuts) for l in layouts),
            -max((l.largest_offcut for l in layouts), default=0))


def default_workers() -> int:
    """80 % of the cores, at least one."""
    return max(1, (os.cpu_count() or 1) * 8 // 10)


_FIXED = [(s, p, o) for o in ("area", "long") for s in SELECTS for p in SPLITS]


def variant_for(index: int, seed: int) -> Variant:
    """The index-th candidate: first every fixed combination, then random ones drawn from the seed."""
    if index < len(_FIXED):
        select, split, order = _FIXED[index]
        return Variant(select, split, order, 0)
    rng = random.Random(seed * 1_000_003 + index)
    return Variant(rng.choice(SELECTS), rng.choice(SPLITS), "shuffle", rng.randrange(1 << 30))


def _run_batch(items, sheet, kerf, seed, indices):
    """The best (score, index, layouts) of some candidates; runs in a worker process."""
    best = None
    for index in indices:
        layouts = pack(items, sheet, kerf, variant_for(index, seed))
        key = (score(layouts), index)
        if best is None or key < best[:2]:
            best = (key[0], index, layouts)
    return best


def _consider(best, result, on_progress):
    """Keep the better of the current best (a Solution) and a batch result; report an improvement."""
    if result is not None and result[0] < best.score:
        best = Solution(tuple(result[2]), result[0])
        if on_progress:
            on_progress(best)
    return best


def optimize(items, sheet, kerf, *, seconds=15.0, iterations=None, workers=None, seed=0, start=None,
             on_progress=None, cancel=None) -> Solution:
    """Search many variants and keep the best. Candidate 0 runs in the calling process, so there is always a result
    (CutError if a piece fits no sheet). `iterations` (a count of candidates) replaces the clock; the result is
    never worse than `start`. Same seed and iterations give the same result whatever the number of workers."""
    items = list(items)
    first = pack(items, sheet, kerf, variant_for(0, seed))
    best = Solution(tuple(first), score(first))
    if start is not None and start.score <= best.score:
        best = start
    elif on_progress:
        on_progress(best)
    workers = default_workers() if workers is None else max(1, workers)
    deadline = None if iterations is not None else time.monotonic() + seconds
    limit = iterations if iterations is not None else float("inf")
    pool = None
    if workers > 1:
        try:
            pool = ProcessPoolExecutor(max_workers=workers)
        except (OSError, RuntimeError, ValueError, ImportError):
            pool = None
    next_index = 1
    try:
        while next_index < limit:
            if cancel is not None and cancel():
                break
            if deadline is not None and time.monotonic() >= deadline:
                break
            per_round = workers if pool else 1
            chunks = []
            for _ in range(per_round):
                stop = min(next_index + BATCH, limit)
                if stop <= next_index:
                    break
                chunks.append(range(next_index, stop))
                next_index = stop
            results = None
            if pool:
                try:
                    futures = [pool.submit(_run_batch, items, sheet, kerf, seed, list(c)) for c in chunks]
                    results = [f.result() for f in futures]
                except Exception:           # broken pool: finish in the calling process
                    pool.shutdown(wait=False, cancel_futures=True)
                    pool = None
            if results is None:
                results = [_run_batch(items, sheet, kerf, seed, list(c)) for c in chunks]
            for result in sorted((r for r in results if r), key=lambda r: (r[0], r[1])):
                best = _consider(best, result, on_progress)
    finally:
        if pool:
            pool.shutdown(wait=False, cancel_futures=True)
    return best
