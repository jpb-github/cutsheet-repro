"""Parameter form generated from the catalogue, with live validation.

One widget per Param; every edit goes through Part.normalise, so the rules and messages are exactly the CLI's and the
cache's (the form invents none). Errors show under the field that the ParamError names. A length is a text box plus a
mm / cm / in combo; its form value is the text with the unit added ("18" + "cm" = "18cm"). Used by the tabs of the parts.
"""
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from app.theme import set_invalid
from core.catalogue import Part
from core.params import Param, ParamError

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
        for p in part.params:
            label = QLabel(p.label)
            label.setObjectName("fieldLabel")
            label.setMinimumWidth(190)
            label.setContentsMargins(0, 6, 0, 0)       # lines up with the text of the field beside it
            form.addRow(label, self._row(p))
        layout.addLayout(form)
        layout.addWidget(self.summary_label)
        layout.addStretch(1)
        self._valid = True
        self._revalidate(emit=False)

    def _row(self, p: Param) -> QWidget:
        if p.kind == "bool":
            w = QCheckBox()
            w.setChecked(bool(p.default))
            w.toggled.connect(self._revalidate)
            edit = w
        elif p.kind == "length":
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
            w = QLineEdit(_default_text(p))
            w.textChanged.connect(self._revalidate)
            edit = w
        w.setObjectName("field_" + p.name)
        w.setToolTip("%s (default: %s)" % (p.help or p.label, _default_text(p) or "generator default"))
        self._invalid_target = getattr(self, "_invalid_target", {})
        self._invalid_target[p.name] = edit
        error = QLabel()
        error.setObjectName("fieldError")
        self._widgets[p.name] = w
        self._error_labels[p.name] = error
        row = QWidget()
        row.setMaximumWidth(320)
        box = QVBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        box.addWidget(w)
        box.addWidget(error)
        return row

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
            w.setText("" if value is None else str(value))

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
        self._errors, self._summary = {}, ""
        try:
            self.part.normalise(self.raw())
        except ParamError as e:
            self._errors[e.param] = e.message
            label = next((p.label for p in self.part.params if p.name == e.param), e.param)
            self._summary = "%s: %s" % (label, e.message)
        for name, lab in self._error_labels.items():
            lab.setText(self._errors.get(name, ""))
            set_invalid(self._invalid_target[name], name in self._errors)
        self.summary_label.setText(self._summary)
        valid = not self._errors
        flipped = valid != self._valid
        self._valid = valid
        if emit:
            self.changed.emit()
            if flipped:
                self.validity_changed.emit(valid)
