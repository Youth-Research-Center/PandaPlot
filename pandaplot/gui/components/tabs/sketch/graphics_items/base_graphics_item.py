from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsItem

from pandaplot.models.project.items.sketch import SketchElement


def get_pen_style(style_str: str) -> Qt.PenStyle:
    mapping = {
        "solid": Qt.SolidLine,
        "dashed": Qt.DashLine,
        "dotted": Qt.DotLine,
        "dash_dot": Qt.DashDotLine,
    }
    return mapping.get(style_str.lower(), Qt.SolidLine)


class BaseGraphicsItem(QGraphicsItem):
    """Base QGraphicsItem wrapper for a SketchElement model."""

    def __init__(self, element: SketchElement, parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self.element: SketchElement = element
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.update_from_element()

    def update_from_element(self) -> None:
        self.setPos(self.element.x, self.element.y)
        self.setRotation(self.element.rotation)

    def get_pen(self) -> QPen:
        pen = QPen(QColor(self.element.stroke_color))
        pen.setWidthF(max(0.5, self.element.stroke_width))
        pen.setStyle(get_pen_style(self.element.stroke_style))
        return pen

    def get_brush(self) -> QBrush:
        if not self.element.fill_color or self.element.fill_color.lower() == "none":
            return QBrush(Qt.NoBrush)
        return QBrush(QColor(self.element.fill_color))

    def sync_to_element(self) -> None:
        pos = self.pos()
        self.element.x = pos.x()
        self.element.y = pos.y()
        self.element.rotation = self.rotation()
