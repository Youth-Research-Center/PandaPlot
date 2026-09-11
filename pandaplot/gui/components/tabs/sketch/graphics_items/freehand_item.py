from typing import Optional

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QPainterPathStroker
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from pandaplot.gui.components.tabs.sketch.graphics_items.base_graphics_item import BaseGraphicsItem
from pandaplot.models.project.items.sketch import FreehandElement


class FreehandGraphicsItem(BaseGraphicsItem):
    """QGraphicsItem representing a freehand stroke path."""

    def __init__(self, element: FreehandElement, parent: Optional[QGraphicsItem] = None):
        self.element: FreehandElement = element
        self._path = QPainterPath()
        super().__init__(element, parent)

    def update_from_element(self) -> None:
        super().update_from_element()
        self._path = QPainterPath()
        if self.element.points:
            self._path.moveTo(QPointF(*self.element.points[0]))
            for pt in self.element.points[1:]:
                self._path.lineTo(QPointF(*pt))

    def boundingRect(self) -> QRectF:
        pen_w = max(5.0, self.element.stroke_width)
        return self._path.boundingRect().adjusted(-pen_w, -pen_w, pen_w, pen_w)

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(max(8.0, self.element.stroke_width))
        return stroker.createStroke(self._path)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        painter.setPen(self.get_pen())
        painter.setBrush(self.get_brush())
        painter.drawPath(self._path)
