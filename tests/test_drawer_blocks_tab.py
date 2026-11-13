import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import settings  # noqa: E402
from app.drawer_blocks_tab import DrawerBlocksTab  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def type_into(tab, name, text):
    tab.form.widget(name).number.setText(text)


def test_the_list_merges_the_pieces_and_the_hardware(qapp):
    tab = DrawerBlocksTab()
    assert [tab.table.horizontalHeaderItem(i).text() for i in range(6)] == ["Item", "Qty", "Length", "Width", "Thickness", "Material / detail"]
    assert tab.rows() == [
        ("Box top and bottom", "2", "756", "512", "18", "thick"),
        ("Box side", "2", "310", "512", "18", "thick"),
        ("Box back", "1", "756", "346", "6", "thin"),
        ("Drawer side", "4", "500", "141.5", "18", "thick"),
        ("Drawer front and back", "4", "658", "141.5", "18", "thick"),
        ("Drawer bottom", "2", "694", "500", "6", "thin"),
        ("Facade", "2", "756", "165.5", "18", "thick"),
        ("Pocket screw, box", "20", "", "", "", "32 mm, fine thread (18 mm sheet); 5 per joint x 4 joints"),
        ("Pocket screw, drawers", "16", "", "", "", "32 mm, fine thread (18 mm sheet); 2 per corner x 4 corners x 2 drawers"),
        ("Drawer pull", "2", "", "", "", "one per drawer"),
    ]
    assert tab.total_label.text() == "17 pieces in 7 lines, 38 hardware items (mm)" and tab.generate_button.isEnabled()


def test_the_list_follows_the_form(qapp):
    tab = DrawerBlocksTab()
    tab.form.widget("drawers").setText("3")
    assert tab.rows()[6][1] == "3" and tab.rows()[6][3] == "108.667"
    assert tab.rows()[-1][:2] == ("Drawer pull", "3")                          # one pull per drawer
    type_into(tab, "slide_clearance", "0")
    assert tab.rows()[5][2] == "696"
    tab.form.widget("drawers").setText("1")                                   # a tall drawer (294 mm): 3 screws per corner
    assert tab.rows()[-2][1] == "12" and "3 per corner" in tab.rows()[-2][5]


def test_a_slide_higher_than_the_drawer_is_refused(qapp):
    tab = DrawerBlocksTab()
    type_into(tab, "slide_height", "150")
    assert not tab.generate_button.isEnabled() and not tab.view_button.isEnabled() and tab.rows() == []
    assert "drawer side height" in tab.form.field_error("slide_height")
    type_into(tab, "slide_height", "141.5")
    assert tab.generate_button.isEnabled() and tab.view_button.isEnabled() and len(tab.rows()) == 10


def test_the_view_button_draws_the_block_and_then_follows_the_form(qapp):
    tab = DrawerBlocksTab()
    assert [tab.splitter.widget(i) is not None for i in (0, 1)] == [True, True] and tab.splitter.orientation() == Qt.Vertical
    assert tab.view_button.text() == "View" and not tab.view.has_view()
    tab.resize(1100, 700)
    tab.show()
    qapp.processEvents()
    from PySide6.QtCore import QPoint
    view_x, generate_x = (b.mapTo(tab, QPoint(0, 0)).x() for b in (tab.view_button, tab.generate_button))
    assert view_x < generate_x                                                # View is on the left of Generate
    tab.view_button.click()
    assert tab.view.has_view()
    one = tab.view.face_count()
    tab.form.widget("drawers").setText("1")
    assert tab.view.has_view() and tab.view.face_count() < one                  # fewer drawers: fewer faces
    type_into(tab, "slide_height", "400")
    assert not tab.view.has_view()                                              # invalid: nothing to draw
    assert tab.view.grab().toImage().width() > 0                               # it paints without error


def test_generate_emits_the_part_with_normalised_values(qapp):
    tab = DrawerBlocksTab()
    got = []
    tab.generate_requested.connect(lambda part, params: got.append((part.key, params)))
    type_into(tab, "width", "76")
    tab.form.widget("width").unit.setCurrentText("cm")
    tab.generate_button.click()
    assert got[0][0] == "drawer_blocks" and got[0][1]["width"] == "760mm" and got[0][1]["drawers"] == 2
    tab.set_busy(True)
    assert not tab.generate_button.isEnabled()


def test_values_are_remembered_and_reset(qapp):
    tab = DrawerBlocksTab()
    tab.form.widget("drawers").setText("4")
    assert settings.load_form("drawer_blocks")["drawers"] == "4"
    again = DrawerBlocksTab()                     # a new launch: the values come back (the tab is kept alive while its form is used)
    assert again.form.params()["drawers"] == 4
    tab.reset_button.click()
    assert tab.form.params()["drawers"] == 2
