"""The PDF of the cutsheet: pages, non-blank rendering, and a write that fails leaves nothing behind."""
import math
import os

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument

from app.cutsheet_pdf import write_pdf
from core import catalogue
from core.cutsheet import build_cutsheet, plan_cutsheet

PART = catalogue.get_part("drawer_blocks")


def example(**raw):
    p = PART.normalise(raw)
    pieces = catalogue.drawer_block_pieces(p)
    return build_cutsheet(pieces, catalogue.drawer_block_hardware(p), p, plan_cutsheet(p, iterations=30, workers=1))


def render(path):
    doc = QPdfDocument(None)
    assert doc.load(str(path)) == QPdfDocument.Error.None_
    images = [doc.render(i, QSize(800, 566)) for i in range(doc.pageCount())]
    return doc, images


def test_pdf_of_the_example_has_summary_sheets_and_piece_pages(tmp_path):
    cs = example()
    path = tmp_path / "out.pdf"
    write_pdf(cs, path)
    doc, images = render(path)
    # 1 summary + 2 sheets + the pieces, four per page (7 pieces: 2 pages)
    assert doc.pageCount() == 1 + len(cs.sheets) + math.ceil(len(cs.labels) / 4)
    for i, img in enumerate(images):
        assert not img.isNull()
        assert img.width() > img.height()                         # landscape
        px = {img.pixel(x, y) for x in range(0, img.width(), 7) for y in range(0, img.height(), 7)}
        assert len(px) > 1, "page %d is blank" % (i + 1)
    doc.close()


def test_many_small_sheets_give_one_page_each(tmp_path):
    cs = example(sheet_length="800mm", sheet_width="800mm")
    assert len(cs.sheets) > 4
    path = tmp_path / "small.pdf"
    write_pdf(cs, path)
    doc, images = render(path)
    assert doc.pageCount() >= 1 + len(cs.sheets) + math.ceil(len(cs.labels) / 4)
    doc.close()


def test_failed_write_raises_and_leaves_no_file(tmp_path):
    cs = example()
    path = tmp_path / "missing folder" / "out.pdf"
    with pytest.raises(OSError):
        write_pdf(cs, path)
    assert not path.exists() and not path.parent.exists()


def test_locked_target_leaves_nothing_half_written(tmp_path):
    cs = example()
    path = tmp_path / "out.pdf"
    path.mkdir()                                                   # a folder in the way: the final rename fails
    with pytest.raises(OSError):
        write_pdf(cs, path)
    assert sorted(os.listdir(tmp_path)) == ["out.pdf"]


def test_existing_pdf_is_replaced(tmp_path):
    cs = example()
    path = tmp_path / "out.pdf"
    path.write_bytes(b"old")
    write_pdf(cs, path)
    assert path.read_bytes().startswith(b"%PDF")
    assert sorted(os.listdir(tmp_path)) == ["out.pdf"]
