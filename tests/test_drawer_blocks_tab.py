import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from app import settings  # noqa: E402
from app.drawer_blocks_tab import DrawerBlocksTab  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def type_into(tab, name, text):
    tab.form.widget(name).setText(text)


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
    assert not tab.generate_button.isEnabled() and tab.rows() == []
    assert "drawer side height" in tab.form.field_error("slide_height")
    type_into(tab, "slide_height", "141.5")
    assert tab.generate_button.isEnabled() and len(tab.rows()) == 10


def test_the_form_groups_the_dimensions_on_lines_with_one_letter_labels(qapp):
    tab = DrawerBlocksTab()
    assert tab.form.lines() == [
        ("Space", ["width", "height", "depth"]),
        ("Clearance", ["box_clearance", "drawer_clearance", "slide_clearance"]),
        ("Drawers", ["drawers"]),
        ("Thickness", ["thick", "thin"]),
        ("Slide", ["slide_thickness", "slide_length", "slide_height"]),
        ("Screws", ["screw_spacing"]),
        ("Sheets", ["per_thickness"]),
        ("Sheet", ["sheet_length", "sheet_width"]),
        ("Thick sheet", ["thick_sheet_length", "thick_sheet_width"]),
        ("Thin sheet", ["thin_sheet_length", "thin_sheet_width"]),
        ("Saw", ["kerf"]),
    ]
    letters = [l.text() for l in tab.form.findChildren(QLabel, "fieldLetter")]
    assert letters == ["W", "H", "D", "Box", "Drawer", "Slide", "N", "Thick", "Thin", "T", "L", "H", "Spacing", "L", "W", "L", "W", "L", "W", "Kerf"]
    assert [l.text() for l in tab.form.findChildren(QLabel, "fieldUnit")] == ["mm"] * 9      # one unit at the end of each line of lengths
    assert "Available width" in tab.form.widget("width").toolTip() and "760mm" in tab.form.widget("width").toolTip()
    type_into(tab, "width", "76cm")                                          # typed units are still understood
    assert tab.form.params()["width"] == "760mm"
    type_into(tab, "slide_length", "20in")
    assert tab.form.params()["slide_length"] == "508mm"


def test_an_error_shows_under_its_line_and_only_there(qapp):
    tab = DrawerBlocksTab()
    tab.show()
    type_into(tab, "slide_height", "150")
    shown = [(n, tab.form.error_label(n).text()) for n in ("slide_length", "slide_height", "width") if tab.form.error_label(n).isVisible()]
    assert len(shown) == 1 and shown[0][0] == "slide_height" and "drawer side height" in shown[0][1]
    type_into(tab, "slide_height", "35")
    assert not any(tab.form.error_label(n).isVisible() for n in ("slide_length", "slide_height", "width"))


def test_the_view_is_always_drawn_and_follows_the_form(qapp):
    tab = DrawerBlocksTab()
    assert not hasattr(tab, "view_button") and tab.view.has_view()           # no View button: drawn from the start
    one = tab.view.face_count()
    tab.form.widget("drawers").setText("1")
    assert tab.view.has_view() and tab.view.face_count() < one                  # fewer drawers: fewer faces
    type_into(tab, "slide_height", "400")
    assert not tab.view.has_view()                                              # invalid: nothing to draw, a message instead
    type_into(tab, "slide_height", "35")
    assert tab.view.has_view()
    tab.show()
    qapp.processEvents()
    assert tab.view.grab().toImage().width() > 0                               # it paints without error


def test_generate_emits_the_part_with_normalised_values(qapp):
    tab = DrawerBlocksTab()
    got = []
    tab.generate_requested.connect(lambda part, params: got.append((part.key, params)))
    type_into(tab, "width", "76cm")
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


def test_the_help_is_on_the_row_of_the_buttons_at_their_left(qapp):
    from PySide6.QtCore import QPoint
    tab = DrawerBlocksTab()
    tab.resize(1200, 760)
    tab.show()
    qapp.processEvents()
    hint, reset, generate = (w.mapTo(tab, QPoint(0, 0)) for w in (tab.hint_label, tab.reset_button, tab.generate_button))
    assert hint.x() < reset.x() < generate.x()
    assert tab.hint_label.geometry().right() < tab.reset_button.geometry().left()                       # on the left of the buttons
    assert hint.y() < reset.y() + tab.reset_button.height() and reset.y() < hint.y() + tab.hint_label.height()    # on the same row


def test_the_sheet_lines_follow_the_one_size_per_thickness_box(qapp):
    from PySide6.QtWidgets import QCheckBox
    tab = DrawerBlocksTab()
    tab.show()
    qapp.processEvents()
    box = tab.form.widget("per_thickness")
    assert isinstance(box, QCheckBox) and box.text() == "One size per thickness" and not box.isChecked()
    visible = lambda: [t for t in ("Sheets", "Sheet", "Thick sheet", "Thin sheet", "Saw") if tab.form.line_visible(t)]
    assert visible() == ["Sheets", "Sheet", "Saw"]
    box.setChecked(True)
    assert visible() == ["Sheets", "Thick sheet", "Thin sheet", "Saw"]
    box.setChecked(False)
    assert visible() == ["Sheets", "Sheet", "Saw"]


def test_a_sheet_that_is_too_small_is_refused_under_the_sheet_line(qapp):
    tab = DrawerBlocksTab()
    tab.show()
    type_into(tab, "sheet_length", "700")
    type_into(tab, "sheet_width", "700")
    assert not tab.generate_button.isEnabled() and tab.rows() == []
    assert tab.form.error_label("sheet_length").isVisible() and "Box top and bottom" in tab.form.error_label("sheet_length").text()
    type_into(tab, "sheet_length", "1200")
    type_into(tab, "sheet_width", "1200")
    assert tab.generate_button.isEnabled()
    tab.form.widget("per_thickness").setChecked(True)                      # the 700 x 700 style garbage in a hidden line cannot block
    type_into(tab, "sheet_length", "garbage")
    assert tab.generate_button.isEnabled()
