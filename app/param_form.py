"""Parameter form generated from the catalogue, with live validation.

One widget per Param; every edit goes through Part.normalise, so the rules and messages are exactly the CLI's and the
cache's (the form invents none). Errors show under the line of the field that the ParamError names. Parameters that share a
`row` are on one line: the title of the row on the left, then a short label (a letter such as W, H, D, or a short word) and a narrow
field for each, and one "mm" at the end when they are lengths; a typed unit (76cm, 3in) is still understood. A parameter without a
row has its own line; its length is a text box plus a mm / cm / in combo (the form value is the text with the unit added).
Used by the tabs of the parts.
"""
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from app.theme import set_invalid
from core.catalogue import Part
from core.params import Param, ParamError, applies

UNITS = ("mm", "cm", "in")


def _scrolling(widget: QWidget) -> QScrollArea:
    """Put a form in a frameless scroll area so a short window scrolls instead of squeezing the fields."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setWidget(widget)
    return area


def choice_label(choice: str) -> str:
    """How a choice is listed: initial caps on every word ("large thread - t mode" -> "Large Thread - T Mode")."""
    return str(choice).title()


def _default_text(p: Param) -> str:
    return "" if p.default is None else str(p.default)


def _plain(text: str) -> str:
    """A canonical length shown without its unit on a line of lengths ("760mm" -> "760"); anything else as it is."""
    return text[:-2] if text.endswith("mm") and text[:-2].replace(".", "", 1).isdigit() else text


def split_length(text: str) -> tuple[str, str]:
    """("18cm" -> ("18", "cm")); a text without a known unit stays whole with the unit mm."""
    m = re.fullmatch(r"\s*(.*?)\s*(mm|cm|in)\s*", text, re.I)
    return (m.group(1), m.group(2).lower()) if m else (text, "mm")


class LengthField(QWidget):
    """A number box and a unit combo that behave as one text value."""
    edited = Signal()

    def __init__(self):
        super().__init__()
        self.number = QLineEdit()
        self.unit = QComboBox()
        self.unit.addItems(UNITS)
        self.unit.setFixedWidth(70)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.number, 1)
        row.addWidget(self.unit)
        self.number.textChanged.connect(self.edited)
        self.unit.currentTextChanged.connect(self.edited)

    def text(self) -> str:
        return self.number.text().strip() + self.unit.currentText()

    def set_text(self, text: str) -> None:
        number, unit = split_length(text)
        self.unit.blockSignals(True)
        self.unit.setCurrentText(unit)
        self.unit.blockSignals(False)
        self.number.setText(number)


class ParamForm(QWidget):
    changed = Signal()
    validity_changed = Signal(bool)

    def __init__(self, part: Part, parent: QWidget | None = None):
        super().__init__(parent)
        self.part = part
        self._widgets: dict[str, QWidget] = {}
        self._error_labels: dict[str, QLabel] = {}
        self._errors: dict[str, str] = {}
        self._summary = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 24, 0)       # keeps the fields clear of the scroll bar
        layout.setSpacing(10)
        self.summary_label = QLabel()
        self.summary_label.setObjectName("formSummary")
        self.summary_label.setWordWrap(True)
        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(6)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setContentsMargins(0, 0, 0, 0)
        self._lines: list[tuple[str, list[Param]]] = []
        for p in part.params:                                   # consecutive parameters with the same row share a line
            if p.row and self._lines and self._lines[-1][0] == p.row:
                self._lines[-1][1].append(p)
            else:
                self._lines.append((p.row or p.label, [p]))
        self._form = form
        self._line_shown: dict[str, bool] = {}
        for title, params in self._lines:
            label = QLabel(title)
            label.setObjectName("fieldLabel")
            label.setMinimumWidth(115)
            label.setContentsMargins(0, 6, 0, 0)       # lines up with the text of the field beside it
            form.addRow(label, self._line(params))
        layout.addLayout(form)
        layout.addWidget(self.summary_label)
        layout.addStretch(1)
        self._valid = True
        self._revalidate(emit=False)

    def lines(self) -> list[tuple[str, list[str]]]:
        """The lines of the form: the title and the names of the parameters on it."""
        return [(title, [p.name for p in params]) for title, params in self._lines]

    def line_visible(self, title: str) -> bool:
        """Whether the line is shown: a line whose parameters do not apply (their `when` condition) is hidden."""
        return self._line_shown.get(title, True)

    def _update_lines(self) -> None:
        values = {p.name: self._widgets[p.name].isChecked() for p in self.part.params if p.kind == "bool" and not p.when}
        for row, (title, params) in enumerate(self._lines):
            shown = applies(params[0], values)
            self._line_shown[title] = shown
            self._form.setRowVisible(row, shown)

    def error_label(self, name: str) -> QLabel:
        return self._error_labels[name]

    def _line(self, params: list[Param]) -> QWidget:
        shared = bool(params[0].row)
        row = QWidget()
        row.setMaximumWidth(470 if shared else 320)
        box = QVBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        if not shared:
            box.addWidget(self._field(params[0], shared=False))
            box.addWidget(self._error(params[0]))
            return row
        fields = QHBoxLayout()
        fields.setSpacing(6)
        last_length = max((i for i, p in enumerate(params) if p.kind == "length"), default=-1)
        for i, p in enumerate(params):
            field = self._field(p, shared=True)
            if p.kind != "bool":                            # a check box carries its own text
                letter = QLabel(p.short or p.label)
                letter.setObjectName("fieldLetter")
                letter.setToolTip(p.label)
                fields.addWidget(letter)
                field.setMaximumWidth(84)                   # four digits and a decimal point; the line stays compact
            fields.addWidget(field)
            if i == last_length:                            # the unit of the lengths, right after the last one
                unit = QLabel("mm")
                unit.setObjectName("fieldUnit")
                fields.addWidget(unit)
        fields.addStretch(1)
        box.addLayout(fields)
        for p in params:
            box.addWidget(self._error(p))
        return row

    def _error(self, p: Param) -> QLabel:
        error = QLabel()
        error.setObjectName("fieldError")
        error.setWordWrap(True)
        error.setVisible(False)
        self._error_labels[p.name] = error
        return error

    def _field(self, p: Param, shared: bool) -> QWidget:
        if p.kind == "bool":
            w = QCheckBox(p.short or p.label if shared else "")
            w.setChecked(bool(p.default))
            w.toggled.connect(self._revalidate)
            edit = w
        elif p.kind == "length" and not shared:
            w = LengthField()
            w.set_text(_default_text(p))
            w.edited.connect(self._revalidate)
            edit = w.number
        elif p.kind == "choice":
            w = QComboBox()
            w.addItems([choice_label(c) for c in p.choices])         # shown with initial caps on every word; the value is read back case-insensitively
            w.setCurrentIndex(max(0, w.findText(str(p.default), Qt.MatchFixedString)))
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            w.currentTextChanged.connect(self._revalidate)
            edit = w
        else:
            w = QLineEdit(_plain(_default_text(p)) if p.kind == "length" else _default_text(p))
            w.textChanged.connect(self._revalidate)
            edit = w
        w.setObjectName("field_" + p.name)
        w.setToolTip("%s (default: %s)" % (p.help or p.label, _default_text(p) or "generator default"))
        if p.help and p.label not in w.toolTip():
            w.setToolTip("%s: %s" % (p.label, w.toolTip()))
        self._invalid_target = getattr(self, "_invalid_target", {})
        self._invalid_target[p.name] = edit
        self._widgets[p.name] = w
        return w

    def widget(self, name: str) -> QWidget:
        return self._widgets[name]

    def raw(self) -> dict[str, object]:
        out: dict[str, object] = {}
        for p in self.part.params:
            w = self._widgets[p.name]
            if isinstance(w, QCheckBox):
                out[p.name] = w.isChecked()
            elif isinstance(w, LengthField):
                out[p.name] = w.text()
            elif isinstance(w, QComboBox):
                out[p.name] = w.currentText()
            else:
                text = w.text()
                out[p.name] = None if p.kind in ("int", "float") and p.default is None and text.strip() == "" else text
        return out

    def params(self) -> dict[str, object] | None:
        try:
            return self.part.normalise(self.raw())
        except ParamError:
            return None

    def errors(self) -> dict[str, str]:
        return dict(self._errors)

    def field_error(self, name: str) -> str:
        return self._errors.get(name, "")

    def summary_text(self) -> str:
        return self._summary

    def is_valid(self) -> bool:
        return self._valid

    def set_value(self, name: str, value: object) -> None:
        w = self._widgets[name]
        if isinstance(w, QCheckBox):
            w.setChecked(bool(value))
        elif isinstance(w, LengthField):
            w.set_text(str(value))
        elif isinstance(w, QComboBox):
            if w.isEditable():
                w.setEditText(str(value))
            else:                                                    # the items have initial caps, a remembered value may not (case-insensitive)
                index = w.findText(str(value), Qt.MatchFixedString)
                if index >= 0:
                    w.setCurrentIndex(index)
        else:
            p = next(p for p in self.part.params if p.name == name)
            text = "" if value is None else str(value)
            w.setText(_plain(text) if p.kind == "length" else text)

    def restore(self, values: dict) -> None:
        """Put remembered values back: only the parameters of this part, nothing else (a stale or damaged setting is ignored)."""
        for p in self.part.params:
            value = values.get(p.name)
            if isinstance(value, bool) if p.kind == "bool" else isinstance(value, (str, int, float)) and not isinstance(value, bool):
                self.set_value(p.name, value)

    def reset(self) -> None:
        for p in self.part.params:
            self.set_value(p.name, p.default if p.kind == "bool" else _default_text(p))

    def _revalidate(self, *_args, emit: bool = True) -> None:
        self._update_lines()
        self._errors, self._summary = {}, ""
        try:
            self.part.normalise(self.raw())
        except ParamError as e:
            self._errors[e.param] = e.message
            label = next((p.label for p in self.part.params if p.name == e.param), e.param)
            self._summary = "%s: %s" % (label, e.message)
        for name, lab in self._error_labels.items():
            lab.setText(self._errors.get(name, ""))
            lab.setVisible(name in self._errors)
            set_invalid(self._invalid_target[name], name in self._errors)
        self.summary_label.setText(self._summary)
        valid = not self._errors
        flipped = valid != self._valid
        self._valid = valid
        if emit:
            self.changed.emit()
            if flipped:
                self.validity_changed.emit(valid)
