"""The Drawer Blocks tab: the form of the block of drawers (generated from the catalogue), the live table of the pieces to cut and
Generate, which saves the list as a CSV.

It only emits generate_requested(part, params) with the normalised parameters. The table comes from core.drawer_rules through
core.catalogue.drawer_block_pieces; while the form is invalid the table is empty (the form shows the message of the field).
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from app import settings
from app.param_form import ParamForm, _scrolling
from core.catalogue import Part, drawer_block_pieces, get_part
from core.drawer_rules import Piece
from core.params import ParamError

HINT = ("Give the space the block must fit in, facades and box included, all in mm. The box is two sides between a top and a bottom "
        "with a thin back and the facades in front; the drawers are rectangular boxes with the bottom nailed under, on slides "
        "outside of them. Generate saves the list of the pieces as a CSV file.")
COLUMNS = ("Piece", "Material", "Thickness", "Qty", "Length", "Width")


def _num(x: float) -> str:
    return "%g" % x


class DrawerBlocksTab(QWidget):
    generate_requested = Signal(object, dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._part = get_part("drawer_blocks")
        self._busy = False
        self.form = ParamForm(self._part)
        self.form.restore(settings.load_form("drawer_blocks"))
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("pieceTable")
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, len(COLUMNS)):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.total_label = QLabel()
        self.total_label.setObjectName("pieceTotal")
        self.hint_label = QLabel(HINT)
        self.hint_label.setObjectName("hint")
        self.hint_label.setWordWrap(True)
        self.generate_button = QPushButton("Generate")
        self.generate_button.setObjectName("primary")
        self.generate_button.setDefault(True)
        self.generate_button.setCursor(Qt.PointingHandCursor)
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
        buttons.addWidget(self.generate_button)
        right = QVBoxLayout()
        right.addWidget(self.table, 1)
        right.addWidget(self.total_label)
        body = QHBoxLayout()
        body.setSpacing(20)
        body.addWidget(_scrolling(self.form), 3)
        body.addLayout(right, 4)
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
        self.form.changed.connect(self._remember)
        self.generate_button.clicked.connect(self._on_generate)
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

    def rows(self) -> list[tuple[str, ...]]:
        """The text of the table, one tuple per piece."""
        return [tuple(self.table.item(r, c).text() for c in range(self.table.columnCount())) for r in range(self.table.rowCount())]

    def _update_table(self, *_args) -> None:
        params = self.form.params()
        try:
            pieces: list[Piece] = drawer_block_pieces(params) if params is not None else []
        except ParamError:
            pieces = []
        self.table.setRowCount(len(pieces))
        for row, p in enumerate(pieces):
            cells = (p.name, p.material, _num(p.thickness), str(p.qty), _num(p.length), _num(p.width))
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if column >= 2:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, column, item)
        self.total_label.setText("%d pieces in %d lines (mm)" % (sum(p.qty for p in pieces), len(pieces)) if pieces else "")

    def _on_generate(self) -> None:
        params = self.form.params()
        if params is not None:
            self.generate_requested.emit(self._part, params)
