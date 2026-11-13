"""Writes the cutsheet as a PDF (A4 landscape, vector) with Qt: a summary page, one page per sheet (pieces to scale, numbered
cuts, kerf, pocket screw marks, the cut instructions) and pages with every piece drawn large, four to a page.

All drawing is in millimetres of the page (the painter window is 0.1 mm per unit, so pixel-size fonts are in 0.1 mm too).
"""
import math
import os
from pathlib import Path

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

from core.cutsheet import Cutsheet, SheetPlan, item_labels
from core.params import length_mm

PAGE_W, PAGE_H = 297.0, 210.0
MARGIN = 10.0
INK = QColor("#222222")
GREY = QColor("#777777")
CUT = QColor("#c0392b")
SHEET_FILL = QColor("#efefef")
PIECE_FILL = {"thick": QColor("#e9cfa6"), "thin": QColor("#bfd9ea")}
MARK = QColor("#1f4e79")


def _g(x: float) -> str:
    return "%g" % round(x, 3)


class _Draw:
    """Drawing in millimetres on a QPainter whose window is in 0.1 mm."""

    def __init__(self, painter: QPainter):
        self.p = painter

    def font(self, size: float, bold: bool = False):
        f = QFont()
        f.setPixelSize(max(1, round(size * 10)))
        f.setBold(bold)
        self.p.setFont(f)

    def pen(self, color=INK, width: float = 0.2, dash: bool = False):
        pen = QPen(color)
        pen.setWidthF(width * 10)
        if dash:
            pen.setStyle(Qt.DashLine)
        self.p.setPen(pen)

    def line(self, x1, y1, x2, y2):
        self.p.drawLine(QPointF(x1 * 10, y1 * 10), QPointF(x2 * 10, y2 * 10))

    def rect(self, x, y, w, h, fill=None):
        self.p.setBrush(fill if fill is not None else Qt.NoBrush)
        self.p.drawRect(QRectF(x * 10, y * 10, w * 10, h * 10))
        self.p.setBrush(Qt.NoBrush)

    def circle(self, cx, cy, r, fill=None):
        self.p.setBrush(fill if fill is not None else Qt.NoBrush)
        self.p.drawEllipse(QPointF(cx * 10, cy * 10), r * 10, r * 10)
        self.p.setBrush(Qt.NoBrush)

    def text(self, x, y, s, size=3.5, align="l", bold=False, color=INK, vertical=False):
        """Text centred on y (on x when align is 'c'); vertical: turned a quarter, reading upwards."""
        self.font(size, bold)
        self.pen(color)
        flags = {"l": Qt.AlignLeft, "c": Qt.AlignHCenter, "r": Qt.AlignRight}[align] | Qt.AlignVCenter
        box = {"l": (0, 4000), "c": (-2000, 4000), "r": (-4000, 4000)}[align]
        self.p.save()
        self.p.translate(x * 10, y * 10)
        if vertical:
            self.p.rotate(-90)
        self.p.drawText(QRectF(box[0], -100, box[1], 200), flags, s)
        self.p.restore()

    def fits(self, s, size) -> float:
        """Width in mm of the text at this size."""
        self.font(size)
        return self.p.fontMetrics().horizontalAdvance(s) / 10


# ------------------------------------------------------------------ pages

def _header(d: _Draw, title: str, sub: str = ""):
    d.text(MARGIN, 12, title, 6, bold=True)
    if sub:
        d.text(PAGE_W - MARGIN, 12, sub, 3.8, "r", color=GREY)
    d.pen(GREY, 0.2)
    d.line(MARGIN, 17, PAGE_W - MARGIN, 17)


def _footer(d: _Draw, number: int, total: int, cs: Cutsheet):
    d.text(MARGIN, PAGE_H - 6, "Cutsheet Generator  -  kerf %s mm" % _g(cs.kerf), 3, color=GREY)
    d.text(PAGE_W - MARGIN, PAGE_H - 6, "page %d of %d" % (number, total), 3, "r", color=GREY)


def _piece_text(cs: Cutsheet, name: str) -> str:
    piece = cs.label_of(name).piece
    return "%s x %s" % (_g(piece.length), _g(piece.width))


def _summary(d: _Draw, cs: Cutsheet):
    _header(d, "Cutsheet", "%d sheet%s" % (len(cs.sheets), "" if len(cs.sheets) == 1 else "s"))
    p = cs.params
    y = 26
    d.text(MARGIN, y, "Block", 4.5, bold=True)
    y += 7
    lines = ["Space  %s x %s x %s mm" % tuple(_g(length_mm(p[k])) for k in ("width", "height", "depth")),
             "Drawers  %s" % p["drawers"],
             "Thick sheet  %s mm   Thin sheet  %s mm" % (_g(length_mm(p["thick"])), _g(length_mm(p["thin"]))),
             "Saw kerf  %s mm" % _g(cs.kerf)]
    for line in lines:
        d.text(MARGIN, y, line, 3.6)
        y += 5.5
    y += 4
    d.text(MARGIN, y, "Sheets", 4.5, bold=True)
    y += 7
    cols = (MARGIN, MARGIN + 14, MARGIN + 40, MARGIN + 62, MARGIN + 100)
    for x, s in zip(cols, ("No.", "Material", "Thickness", "Size", "Waste")):
        d.text(x, y, s, 3.3, bold=True, color=GREY)
    y += 5.5
    for s in cs.sheets:
        row = (str(s.number), s.material, "%s mm" % _g(s.thickness), "%s x %s" % (_g(s.length), _g(s.width)),
               "%.1f %%" % s.waste_percent)
        for x, t in zip(cols, row):
            d.text(x, y, t, 3.5)
        y += 5.2
    x0 = 160.0
    y = 26
    d.text(x0, y, "Pieces", 4.5, bold=True)
    y += 7
    pcols = (x0, x0 + 10, x0 + 62, x0 + 76, x0 + 100)
    for x, s in zip(pcols, ("Label", "Piece", "Qty", "L x W", "Thick.")):
        d.text(x, y, s, 3.3, bold=True, color=GREY)
    y += 5.5
    for l in cs.labels:
        pc = l.piece
        row = (l.label, pc.name, str(pc.qty), "%s x %s" % (_g(pc.length), _g(pc.width)), _g(pc.thickness))
        for x, t in zip(pcols, row):
            d.text(x, y, t, 3.5)
        y += 5.2
    y += 5
    d.text(x0, y, "Hardware", 4.5, bold=True)
    y += 7
    for h in cs.hardware:
        d.text(x0, y, "%s x %d" % (h.name, h.qty), 3.5, bold=True)
        y += 4.6
        d.text(x0 + 4, y, h.detail, 3.1, color=GREY)
        y += 5.4


def _fit_scale(avail_w, avail_h, w, h) -> float:
    return min(avail_w / w, avail_h / h)


def _marks_on_sheet(d: _Draw, cs: Cutsheet, placed, ox, oy, k):
    d.pen(MARK, 0.2)
    for pl in placed:
        for edge in cs.pocket_marks(pl.label):
            for off in edge.offsets:
                if not pl.rotated:                     # drawn length across: the marks are on the left and right ends
                    cx = pl.x + (0.0 if edge.edge == "left" else pl.w)
                    cy = pl.y + off
                    dx = 1.0 if edge.edge == "left" else -1.0
                    cx_mm, cy_mm = ox + cx * k + dx * 1.3, oy + cy * k
                else:                                  # turned: the ends are the top and bottom
                    cx = pl.x + off
                    cy = pl.y + (0.0 if edge.edge == "left" else pl.h)
                    dy = 1.3 if edge.edge == "left" else -1.3
                    cx_mm, cy_mm = ox + cx * k, oy + cy * k + dy
                d.circle(cx_mm, cy_mm, 0.9, MARK)


def _sheet_drawing(d: _Draw, cs: Cutsheet, sheet: SheetPlan, box):
    bx, by, bw, bh = box
    k = _fit_scale(bw, bh, sheet.length, sheet.width)
    ox, oy = bx, by
    d.pen(INK, 0.3)
    d.rect(ox, oy, sheet.length * k, sheet.width * k, SHEET_FILL)
    for pl in sheet.placed:
        d.pen(INK, 0.2)
        d.rect(ox + pl.x * k, oy + pl.y * k, pl.w * k, pl.h * k, PIECE_FILL[sheet.material])
    _marks_on_sheet(d, cs, sheet.placed, ox, oy, k)
    for cut in sheet.cuts:                             # kerf to scale on the waste side of the line, then the line
        r = cut.rect
        d.pen(CUT, 0.1)
        if cut.vertical:
            d.rect(ox + cut.at * k, oy + r.y * k, cs.kerf * k, r.h * k, CUT)
            d.pen(CUT, 0.25)
            d.line(ox + cut.at * k, oy + r.y * k, ox + cut.at * k, oy + (r.y + r.h) * k)
        else:
            d.rect(ox + r.x * k, oy + cut.at * k, r.w * k, cs.kerf * k, CUT)
            d.pen(CUT, 0.25)
            d.line(ox + r.x * k, oy + cut.at * k, ox + (r.x + r.w) * k, oy + cut.at * k)
    for pl in sheet.placed:
        pw, ph = pl.w * k, pl.h * k
        cx, cy = ox + pl.x * k + pw / 2, oy + pl.y * k + ph / 2
        dims = _piece_text(cs, pl.label) + (" R" if pl.rotated else "")
        size = min(4.0, ph / 3.2)
        if size >= 2.2 and d.fits(dims, size * 0.8) <= pw - 1:
            d.text(cx, cy - size * 0.6, pl.label, size, "c", bold=True)
            d.text(cx, cy + size * 0.7, dims, size * 0.8, "c")
        elif min(pw, ph) >= 3:
            d.text(cx, cy, pl.label, min(3.0, ph - 0.5, pw / 2), "c", bold=True)
    for cut in sheet.cuts:
        r = cut.rect
        cx, cy = ((ox + cut.at * k, oy + r.y * k + 2.6) if cut.vertical else (ox + r.x * k + 2.6, oy + cut.at * k))
        d.pen(CUT, 0.25)
        d.circle(cx, cy, 2.3, QColor("white"))
        d.text(cx, cy, str(cut.number), 2.8, "c", bold=True, color=CUT)
    d.text(ox + sheet.length * k / 2, oy + sheet.width * k + 4, "%s mm" % _g(sheet.length), 3.3, "c", color=GREY)
    d.text(ox + sheet.length * k + 4, oy + sheet.width * k / 2, "%s mm" % _g(sheet.width), 3.3, "c", color=GREY, vertical=True)
    return oy + sheet.width * k + 8


def _instruction_columns(lines, per_column, columns):
    return [lines[i:i + per_column * columns] for i in range(0, len(lines), per_column * columns)] or [[]]


def _sheet_pages(cs: Cutsheet, sheet: SheetPlan) -> list:
    lines = sheet.instructions()
    box = (MARGIN + 2, 22, PAGE_W - 2 * MARGIN - 8, 112)
    k = _fit_scale(box[2], box[3], sheet.length, sheet.width)
    top = 22 + sheet.width * k + 8
    room = PAGE_H - 14 - top
    per_column = max(1, int(room // 4.6) - 1)
    columns = 2
    first_chunks = [lines[:per_column * columns]]
    rest = lines[per_column * columns:]
    per_page = int((PAGE_H - 14 - 28) // 4.6) * columns
    chunks = first_chunks + [rest[i:i + per_page] for i in range(0, len(rest), per_page)]
    pages = []
    for index, chunk in enumerate(chunks):
        def draw(d, sheet=sheet, chunk=chunk, index=index, per_column=per_column):
            title = "Sheet %d - %s %s mm" % (sheet.number, sheet.material, _g(sheet.thickness))
            sub = "%s x %s mm  -  waste %.1f %%" % (_g(sheet.length), _g(sheet.width), sheet.waste_percent)
            _header(d, title + ("" if index == 0 else " (cuts, continued)"), sub)
            if index == 0:
                y = _sheet_drawing(d, cs, sheet, box)
                col_h = per_column
            else:
                y, col_h = 28.0, int((PAGE_H - 14 - 28) // 4.6)
            d.text(MARGIN, y + 2, "Cuts, in this order", 3.8, bold=True)
            d.text(MARGIN + 45, y + 2, "(x, y) is the corner of the part from the top left of the sheet; the saw kerf is on the waste side of each line",
                   3.0, color=GREY)
            colw = (PAGE_W - 2 * MARGIN) / 2
            for n, line in enumerate(chunk):
                col, row = divmod(n, col_h)
                d.text(MARGIN + col * colw, y + 8 + row * 4.6, line, 3.0)
        pages.append(draw)
    return pages


def _piece_cell(d: _Draw, cs: Cutsheet, label, cell):
    cx, cy, cw, ch = cell
    pc = label.piece
    names = item_labels(label)
    copies = "" if pc.qty == 1 else "  (%s ... %s)" % (names[0], names[-1])
    d.text(cx, cy + 3, "%s   %s" % (label.label, pc.name), 4.4, bold=True)
    d.text(cx, cy + 9, "Quantity %d%s  -  %s %s mm" % (pc.qty, copies, pc.material, _g(pc.thickness)), 3.2, color=GREY)
    if cs.pocket_marks(label.label):
        d.text(cx, cy + 14, "Pocket holes in the left and right ends, distances from the top", 3.0, color=MARK)
    area = (cx + 12, cy + 18, cw - 26, ch - 38)
    k = _fit_scale(area[2], area[3], pc.length, pc.width)
    x, y, w, h = area[0], area[1], pc.length * k, pc.width * k
    d.pen(INK, 0.3)
    d.rect(x, y, w, h, PIECE_FILL[pc.material])
    d.text(x + w / 2, y + h + 5, "%s mm" % _g(pc.length), 3.4, "c")
    d.text(x - 5, y + h / 2, "%s mm" % _g(pc.width), 3.4, "c", vertical=True)
    for edge in cs.pocket_marks(label.label):
        ex = x if edge.edge == "left" else x + w
        sign = 1 if edge.edge == "left" else -1
        for off in edge.offsets:
            d.pen(MARK, 0.2)
            d.circle(ex + sign * 3, y + off * k, 1.1, MARK)
            d.text(ex + sign * 6, y + off * k, _g(off), 2.6, "l" if sign > 0 else "r", color=MARK)


def _piece_pages(cs: Cutsheet) -> list:
    pages = []
    cw, ch = (PAGE_W - 2 * MARGIN) / 2, (PAGE_H - 22 - 14) / 2
    for start in range(0, len(cs.labels), 4):
        group = cs.labels[start:start + 4]

        def draw(d, group=group):
            _header(d, "Pieces", "dimensions in mm")
            for n, label in enumerate(group):
                row, col = divmod(n, 2)
                _piece_cell(d, cs, label, (MARGIN + col * cw, 22 + row * ch, cw - 4, ch - 4))
        pages.append(draw)
    return pages


def _pages(cs: Cutsheet) -> list:
    pages = [lambda d: _summary(d, cs)]
    for sheet in cs.sheets:
        pages += _sheet_pages(cs, sheet)
    return pages + _piece_pages(cs)


def write_pdf(cs: Cutsheet, path) -> None:
    """Write the PDF to a temporary file next to `path` and rename it over `path`: a failure leaves nothing half written.
    Raises OSError with a readable message."""
    path = Path(path)
    if not path.parent.is_dir():
        raise OSError("The folder %s does not exist." % path.parent)
    tmp = path.with_name(path.name + ".part")
    try:
        _write(cs, tmp)
        os.replace(tmp, path)
    except OSError as e:
        _remove(tmp)
        raise OSError("Cannot write %s: %s" % (path, e.strerror or e)) from e
    except Exception:
        _remove(tmp)
        raise


def _remove(path: Path):
    try:
        path.unlink()
    except OSError:
        pass


def _write(cs: Cutsheet, path: Path) -> None:
    writer = QPdfWriter(str(path))
    writer.setResolution(600)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageOrientation(QPageLayout.Landscape)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    writer.setTitle("Cutsheet")
    writer.setCreator("Cutsheet Generator")
    painter = QPainter()
    if not painter.begin(writer):
        raise OSError("Cannot start writing the PDF.")
    try:
        painter.setWindow(0, 0, int(PAGE_W * 10), int(PAGE_H * 10))
        painter.setRenderHint(QPainter.Antialiasing)
        d = _Draw(painter)
        pages = _pages(cs)
        for number, draw in enumerate(pages, 1):
            if number > 1:
                writer.newPage()
            draw(d)
            _footer(d, number, len(pages), cs)
    finally:
        painter.end()
    del painter, writer
    if not path.exists() or path.stat().st_size == 0:
        raise OSError("The PDF was not written.")
