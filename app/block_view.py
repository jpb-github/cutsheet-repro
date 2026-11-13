"""The 2D view of the block of drawers seen in perspective: a widget that paints the faces of core.drawer_view far to near."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QWidget

from app.theme import INK, LINE, MUTED
from core.drawer_view import Box, exterior, project_faces

KIND_COLORS = {"thick": "#B8885A", "thin": "#DDC598", "facade": "#CFA877", "slide": "#9AA5AA", "pull": "#2B3840"}
MARGIN = 14


class BlockView(QWidget):
    """Shows the closed block (set_boxes: its exterior) or a message (set_message) when there is nothing to draw."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("blockView")
        self.setMinimumHeight(160)
        self._faces = []
        self._message = "Press View to draw the block."

    def set_boxes(self, boxes: list[Box]) -> None:
        self._faces = project_faces(exterior(boxes)) if boxes else []
        self._message = "" if boxes else self._message
        self.update()

    def set_message(self, text: str) -> None:
        self._faces, self._message = [], text
        self.update()

    def has_view(self) -> bool:
        return bool(self._faces)

    def face_count(self) -> int:
        return len(self._faces)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        p.setPen(QPen(QColor(LINE)))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if not self._faces:
            p.setPen(QColor(MUTED))
            p.drawText(self.rect(), Qt.AlignCenter | Qt.TextWordWrap, self._message)
            return
        xs = [pt[0] for f in self._faces for pt in f.points]
        ys = [pt[1] for f in self._faces for pt in f.points]
        width, height = max(xs) - min(xs), max(ys) - min(ys)
        scale = min((self.width() - 2 * MARGIN) / width, (self.height() - 2 * MARGIN) / height)
        ox = (self.width() - scale * width) / 2 - scale * min(xs)
        oy = (self.height() - scale * height) / 2 + scale * max(ys)          # y of the projection points up, the screen's down
        p.setPen(QPen(QColor(INK), 0.8))
        for f in self._faces:
            base = QColor(KIND_COLORS[f.kind])
            p.setBrush(QBrush(QColor(int(base.red() * f.shade), int(base.green() * f.shade), int(base.blue() * f.shade))))
            p.drawPolygon(QPolygonF([QPointF(ox + scale * x, oy - scale * y) for x, y in f.points]))
