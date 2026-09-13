from typing import Optional

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from pandaplot.gui.components.tabs.sketch.graphics_items.base_graphics_item import BaseGraphicsItem
from pandaplot.models.project.items.sketch import WireElement


class WireGraphicsItem(BaseGraphicsItem):
    """QGraphicsItem representing a wire connecting circuit components."""

    def __init__(self, element: WireElement, parent: Optional[QGraphicsItem] = None):
        self.element: WireElement = element
        super().__init__(element, parent)

    def boundingRect(self) -> QRectF:
        if not self.element.waypoints:
            return QRectF(0, 0, 0, 0)

        xs = [p[0] for p in self.element.waypoints]
        ys = [p[1] for p in self.element.waypoints]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w = max(1.0, max_x - min_x)
        h = max(1.0, max_y - min_y)

        pen_w = self.element.stroke_width + 4.0
        return QRectF(min_x, min_y, w, h).adjusted(-pen_w, -pen_w, pen_w, pen_w)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        if not self.element.waypoints:
            return path

        path.moveTo(self.element.waypoints[0][0], self.element.waypoints[0][1])
        for p in self.element.waypoints[1:]:
            path.lineTo(p[0], p[1])

        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        if not self.element.waypoints:
            return

        painter.setPen(self.get_pen())
        path = self.shape()
        painter.drawPath(path)
