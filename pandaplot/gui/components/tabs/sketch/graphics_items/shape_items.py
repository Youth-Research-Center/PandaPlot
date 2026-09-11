from typing import Optional

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from pandaplot.gui.components.tabs.sketch.graphics_items.base_graphics_item import BaseGraphicsItem
from pandaplot.models.project.items.sketch import EllipseElement, RectangleElement


class RectangleGraphicsItem(BaseGraphicsItem):
    """QGraphicsItem representing a rectangle element."""

    def __init__(self, element: RectangleElement, parent: Optional[QGraphicsItem] = None):
        self.element: RectangleElement = element
        super().__init__(element, parent)

    def boundingRect(self) -> QRectF:
        pen_w = self.element.stroke_width
        return QRectF(0, 0, self.element.width, self.element.height).adjusted(-pen_w, -pen_w, pen_w, pen_w)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        if self.element.corner_radius > 0:
            path.addRoundedRect(
                0, 0, self.element.width, self.element.height,
                self.element.corner_radius, self.element.corner_radius
            )
        else:
            path.addRect(0, 0, self.element.width, self.element.height)
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        painter.setPen(self.get_pen())
        painter.setBrush(self.get_brush())
        if self.element.corner_radius > 0:
            painter.drawRoundedRect(
                0, 0, self.element.width, self.element.height,
                self.element.corner_radius, self.element.corner_radius
            )
        else:
            painter.drawRect(0, 0, self.element.width, self.element.height)


class EllipseGraphicsItem(BaseGraphicsItem):
    """QGraphicsItem representing an ellipse element."""

    def __init__(self, element: EllipseElement, parent: Optional[QGraphicsItem] = None):
        self.element: EllipseElement = element
        super().__init__(element, parent)

    def boundingRect(self) -> QRectF:
        pen_w = self.element.stroke_width
        return QRectF(0, 0, self.element.rx * 2, self.element.ry * 2).adjusted(-pen_w, -pen_w, pen_w, pen_w)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(0, 0, self.element.rx * 2, self.element.ry * 2)
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        painter.setPen(self.get_pen())
        painter.setBrush(self.get_brush())
        painter.drawEllipse(0, 0, self.element.rx * 2, self.element.ry * 2)
