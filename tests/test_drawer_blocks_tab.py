import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app import settings  # noqa: E402
from app.drawer_blocks_tab import DrawerBlocksTab  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def type_into(tab, name, text):
    tab.form.widget(name).number.setText(text)


def test_the_table_shows_the_example_of_the_spreadsheet(qapp):
    tab = DrawerBlocksTab()
    assert tab.rows() == [
        ("Box top and bottom", "thick", "18", "2", "756", "512"),
        ("Box side", "thick", "18", "2", "310", "512"),
        ("Box back", "thin", "6", "1", "756", "346"),
        ("Drawer side", "thick", "18", "4", "500", "141.5"),
        ("Drawer front and back", "thick", "18", "4", "658", "141.5"),
        ("Drawer bottom", "thin", "6", "2", "694", "500"),
        ("Facade", "thick", "18", "2", "756", "165.5"),
    ]
    assert tab.total_label.text() == "17 pieces in 7 lines (mm)" and tab.generate_button.isEnabled()


def test_the_table_follows_the_form(qapp):
    tab = DrawerBlocksTab()
    tab.form.widget("drawers").setText("3")
    assert tab.rows()[-1][3] == "3" and tab.rows()[-1][5] == "108.667"
    type_into(tab, "slide_clearance", "0")
    assert tab.rows()[5][4] == "696"


def test_a_slide_higher_than_the_drawer_is_refused(qapp):
    tab = DrawerBlocksTab()
    type_into(tab, "slide_height", "150")
    assert not tab.generate_button.isEnabled() and tab.rows() == []
    assert "drawer side height" in tab.form.field_error("slide_height")
    type_into(tab, "slide_height", "141.5")
    assert tab.generate_button.isEnabled() and len(tab.rows()) == 7


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
