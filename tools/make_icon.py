"""Draw the application icon: python tools/make_icon.py [--out app/assets]

Writes cutsheet.ico (16, 24, 32, 48, 64, 128 and 256 px, PNG-compressed) and cutsheet.png (256 px). Same style as the Multiboard
Generator: a dark slate tile with a sheet cut into pieces by edge-to-edge (guillotine) cuts, the saw kerf between them, one piece in the accent red.
Needs PySide6 only (offscreen is fine); re-run it after changing the colours
in app/theme.py and commit the result: the window uses app/assets/cutsheet.ico.
"""
import argparse
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QPainter  # noqa: E402

from app.theme import ACCENT, PAPER, SLATE  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)
# The sheet (36, 52) to (220, 204) on the 256 grid, cut edge to edge: one cut across the sheet, then the top row in two, the
# right one in two again, and the bottom row in three. (x, y, w, h); the 6 px between them is the kerf.
PIECES = ((36, 52, 100, 84), (142, 52, 78, 39), (142, 97, 78, 39), (36, 142, 57, 62), (99, 142, 58, 62), (163, 142, 57, 62))
RED = 4                                                    # the piece in the accent red


def draw(size: int) -> QImage:
    """One square image; the design is on a 256 grid and scaled."""
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 256.0, size / 256.0)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(SLATE)))
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 54, 54)
    for index, (x, y, w, h) in enumerate(PIECES):
        p.setBrush(QBrush(QColor(ACCENT if index == RED else PAPER)))
        p.drawRoundedRect(QRectF(x, y, w, h), 6, 6)
    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(data)


def build_ico(images: dict[int, bytes]) -> bytes:
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, blob in images.items():
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(blob), offset + len(blobs))
        blobs += blob
    return head + entries + blobs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "app" / "assets"))
    args = ap.parse_args(argv)
    QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    images = {s: png_bytes(draw(s)) for s in SIZES}
    (out / "cutsheet.ico").write_bytes(build_ico(images))
    (out / "cutsheet.png").write_bytes(images[256])
    print("wrote %s (%d sizes)" % (out / "cutsheet.ico", len(images)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
