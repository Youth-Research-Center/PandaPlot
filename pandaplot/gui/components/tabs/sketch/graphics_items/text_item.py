from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from pandaplot.gui.components.tabs.sketch.graphics_items.base_graphics_item import BaseGraphicsItem
from pandaplot.models.project.items.sketch import TextElement


class TextGraphicsItem(BaseGraphicsItem):
    """QGraphicsItem representing a text label."""

    def __init__(self, element: TextElement, parent: Optional[QGraphicsItem] = None):
        self.element: TextElement = element
        super().__init__(element, parent)

    def get_font(self) -> QFont:
        font = QFont(self.element.font_family, self.element.font_size)
        font.setBold(self.element.is_bold)
        font.setItalic(self.element.is_italic)
        return font

    def boundingRect(self) -> QRectF:
        font = self.get_font()
        fm = QFontMetricsF(font)
        rect = fm.boundingRect(self.element.text or " ")
        pen_w = self.element.stroke_width
        return rect.adjusted(-pen_w, -pen_w, pen_w, pen_w)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        painter.setFont(self.get_font())
        painter.setPen(self.get_pen())

        align_flags = Qt.AlignmentFlag.TextSingleLine
        if self.element.alignment == "center":
            align_flags |= Qt.AlignmentFlag.AlignHCenter
        elif self.element.alignment == "right":
            align_flags |= Qt.AlignmentFlag.AlignRight
        else:
            align_flags |= Qt.AlignmentFlag.AlignLeft

        rect = self.boundingRect()
        painter.drawText(rect, align_flags, self.element.text)
