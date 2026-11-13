"""Draw the application icon: python tools/make_icon.py [--out app/assets]

Writes cutsheet.ico (16, 24, 32, 48, 64, 128 and 256 px, PNG-compressed) and cutsheet.png (256 px). Same style as the Multiboard
Generator: a dark slate tile with a board cut into pieces (a 2 x 3 layout of rectangles separated by the saw kerf), one in the accent red.
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
W, H, GAP, OX, OY = 60.0, 38.0, 6.0, 32.0, 43.0          # a piece and the kerf on the 256 grid


def piece(x: float, y: float, w: float = W, h: float = H) -> QRectF:
    return QRectF(x, y, w, h)


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
    for row in range(4):
        for col in range(3):
            p.setBrush(QBrush(QColor(ACCENT if (row, col) == (1, 1) else PAPER)))
            p.drawRoundedRect(piece(OX + col * (W + GAP), OY + row * (H + GAP)), 6, 6)
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
