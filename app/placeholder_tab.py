"""An empty tab of the Cutsheet Generator: a titled card that says the screen is not implemented yet.

Every tab starts as this page; each one is replaced by its real screen when its generator exists.
"""
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class PlaceholderTab(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        heading = QLabel(title)
        heading.setObjectName("partTitle")
        rule = QFrame()
        rule.setObjectName("rule")
        hint = QLabel("Nothing here yet: the cutsheets of this tab are not implemented.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        card = QFrame()
        card.setObjectName("card")
        inside = QVBoxLayout(card)
        inside.setContentsMargins(28, 22, 28, 20)
        inside.setSpacing(12)
        inside.addWidget(heading)
        inside.addWidget(rule)
        inside.addWidget(hint)
        inside.addStretch(1)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.addWidget(card, 1)
