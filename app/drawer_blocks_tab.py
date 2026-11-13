"""The Drawer Blocks tab: the form of the block of drawers (generated from the catalogue) on the left; on the right, split in two, the
live list of the pieces and the hardware (one table) and the perspective view of the block. View draws the block, Generate saves the
list as a CSV.

It only emits generate_requested(part, params) with the normalised parameters. The list comes from core.drawer_rules through
core.catalogue; while the form is invalid the list is empty (the form shows the message of the field) and so is the view.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from app import settings
from app.block_view import BlockView
from app.param_form import ParamForm, _scrolling
from core.catalogue import Part, drawer_block_boxes, drawer_block_hardware, drawer_block_pieces, get_part
from core.params import ParamError

HINT = ("Give the space the block must fit in, facades and box included, all in mm. The box is two sides between a top and a bottom "
        "with a thin back and the facades in front; the drawers are rectangular boxes with the bottom nailed under, on slides "
        "outside of them. Pocket screws are chosen from the thickness of the sheet and the length of each joint. View draws the block "
        "in perspective; Generate saves the pieces and the hardware as a CSV file.")
COLUMNS = ("Item", "Qty", "Length", "Width", "Thickness", "Material / detail")
NO_VIEW = "Nothing to draw: the form has an error."


def _num(x: float) -> str:
    return "%g" % x


class DrawerBlocksTab(QWidget):
    generate_requested = Signal(object, dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._part = get_part("drawer_blocks")
        self._busy = False
        self._viewed = False                       # View was pressed: the view then follows the form
        self.form = ParamForm(self._part)
        self.form.restore(settings.load_form("drawer_blocks"))
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("pieceTable")
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        for column in range(len(COLUMNS) - 1):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(len(COLUMNS) - 1, QHeaderView.Stretch)
        self.total_label = QLabel()
        self.total_label.setObjectName("pieceTotal")
        self.view = BlockView()
        self.hint_label = QLabel(HINT)
        self.hint_label.setObjectName("hint")
        self.hint_label.setWordWrap(True)
        self.generate_button = QPushButton("Generate")
        self.generate_button.setObjectName("primary")
        self.generate_button.setDefault(True)
        self.generate_button.setCursor(Qt.PointingHandCursor)
        self.view_button = QPushButton("View")
        self.reset_button = QPushButton("Reset to defaults")
        title = QLabel(self._part.label)
        title.setObjectName("partTitle")
        subtitle = QLabel(self._part.group)
        subtitle.setObjectName("partGroup")
        rule = QFrame()
        rule.setObjectName("rule")
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.reset_button)
        buttons.addWidget(self.view_button)
        buttons.addWidget(self.generate_button)
        listing = QWidget()                                     # the list and its total, the top of the right side
        listing_layout = QVBoxLayout(listing)
        listing_layout.setContentsMargins(0, 0, 0, 0)
        listing_layout.setSpacing(4)
        listing_layout.addWidget(self.table, 1)
        listing_layout.addWidget(self.total_label)
        self.splitter = QSplitter(Qt.Vertical)                 # the right side: the list above, the view below, resizable
        self.splitter.addWidget(listing)
        self.splitter.addWidget(self.view)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizes([1, 1])
        body = QHBoxLayout()
        body.setSpacing(20)
        body.addWidget(_scrolling(self.form), 3)
        body.addWidget(self.splitter, 4)
        card = QFrame()
        card.setObjectName("card")
        inside = QVBoxLayout(card)
        inside.setContentsMargins(28, 22, 28, 20)
        inside.setSpacing(6)
        inside.addWidget(title)
        inside.addWidget(subtitle)
        inside.addSpacing(8)
        inside.addWidget(rule)
        inside.addSpacing(10)
        inside.addLayout(body, 1)
        inside.addWidget(self.hint_label)
        inside.addSpacing(6)
        inside.addLayout(buttons)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.addWidget(card, 1)
        self.form.validity_changed.connect(self._update_button)
        self.form.changed.connect(self._update_table)
        self.form.changed.connect(self._update_view)
        self.form.changed.connect(self._remember)
        self.generate_button.clicked.connect(self._on_generate)
        self.view_button.clicked.connect(self._on_view)
        self.reset_button.clicked.connect(self.form.reset)
        self._update_button()
        self._update_table()

    def _remember(self, *_args) -> None:
        """The last valid values of the form are kept for the next launch."""
        if self.form.is_valid():
            settings.remember_form("drawer_blocks", self.form.raw())

    def current_part(self) -> Part:
        return self._part

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_button()

    def _update_button(self, *_args) -> None:
        self.generate_button.setEnabled(self.form.is_valid() and not self._busy)
        self.view_button.setEnabled(self.form.is_valid())

    def rows(self) -> list[tuple[str, ...]]:
        """The text of the list, one tuple per line: the pieces, then the hardware."""
        return [tuple(self.table.item(r, c).text() for c in range(self.table.columnCount())) for r in range(self.table.rowCount())]

    def _add_row(self, cells: tuple[str, ...]) -> None:
        row = self.table.rowCount()
        self.table.setRowCount(row + 1)
        for column, text in enumerate(cells):
            item = QTableWidgetItem(text)
            if 1 <= column <= 4:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, column, item)

    def _update_table(self, *_args) -> None:
        params = self.form.params()
        try:
            pieces = drawer_block_pieces(params) if params is not None else []
            hardware = drawer_block_hardware(params) if params is not None else []
        except ParamError:
            pieces, hardware = [], []
        self.table.setRowCount(0)
        for p in pieces:
            self._add_row((p.name, str(p.qty), _num(p.length), _num(p.width), _num(p.thickness), p.material))
        for h in hardware:
            self._add_row((h.name, str(h.qty), "", "", "", h.detail))
        self.total_label.setText("%d pieces in %d lines, %d hardware items (mm)" % (
            sum(p.qty for p in pieces), len(pieces), sum(h.qty for h in hardware)) if pieces else "")

    def _draw(self) -> None:
        params = self.form.params()
        try:
            boxes = drawer_block_boxes(params) if params is not None else []
        except ParamError:
            boxes = []
        if boxes:
            self.view.set_boxes(boxes)
        else:
            self.view.set_message(NO_VIEW)

    def _on_view(self) -> None:
        self._viewed = True
        self._draw()

    def _update_view(self, *_args) -> None:
        """Once the view has been asked for it follows the form (and says so when the form is invalid)."""
        if self._viewed:
            self._draw()

    def _on_generate(self) -> None:
        params = self.form.params()
        if params is not None:
            self.generate_requested.emit(self._part, params)
