from typing import Optional

from PySide6.QtCore import QLineF, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QPainterPathStroker
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from pandaplot.gui.components.tabs.sketch.graphics_items.base_graphics_item import BaseGraphicsItem
from pandaplot.models.project.items.sketch import LineElement


class LineGraphicsItem(BaseGraphicsItem):
    """QGraphicsItem representing a line segment."""

    def __init__(self, element: LineElement, parent: Optional[QGraphicsItem] = None):
        self.element: LineElement = element
        super().__init__(element, parent)

    def boundingRect(self) -> QRectF:
        pen_w = max(5.0, self.element.stroke_width)
        rect = QRectF(
            min(self.element.x1, self.element.x2),
            min(self.element.y1, self.element.y2),
            abs(self.element.x2 - self.element.x1),
            abs(self.element.y2 - self.element.y1),
        )
        return rect.adjusted(-pen_w, -pen_w, pen_w, pen_w)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(self.element.x1, self.element.y1)
        path.lineTo(self.element.x2, self.element.y2)

        stroker = QPainterPathStroker()
        stroker.setWidth(max(8.0, self.element.stroke_width))
        return stroker.createStroke(path)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        painter.setPen(self.get_pen())
        painter.drawLine(QLineF(self.element.x1, self.element.y1, self.element.x2, self.element.y2))
        self.paint_selection_outline(painter)
