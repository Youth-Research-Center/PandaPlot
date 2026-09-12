from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem

from pandaplot.models.project.items.sketch import SketchElement


def get_pen_style(style_str: str) -> Qt.PenStyle:
    mapping = {
        "solid": Qt.SolidLine,
        "dashed": Qt.DashLine,
        "dotted": Qt.DotLine,
        "dash_dot": Qt.DashDotLine,
    }
    return mapping.get(style_str.lower(), Qt.SolidLine)


class ResizeHandleItem(QGraphicsRectItem):
    """Square resize handle rendered on selection bounding box corners."""

    HANDLE_SIZE = 8.0

    def __init__(self, position_key: str, parent: Optional[QGraphicsItem] = None):
        half = self.HANDLE_SIZE / 2.0
        super().__init__(-half, -half, self.HANDLE_SIZE, self.HANDLE_SIZE, parent)
        self.position_key: str = position_key
        self.setPen(QPen(QColor("#0078D4"), 1.0))
        self.setBrush(QBrush(QColor("#FFFFFF")))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)


class BaseGraphicsItem(QGraphicsItem):
    """Base QGraphicsItem wrapper for a SketchElement model with dashed bounding box outline & resize handles."""

    def __init__(self, element: SketchElement, parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self.element: SketchElement = element
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.handles: dict[str, ResizeHandleItem] = {}
        self._create_handles()
        self.update_from_element()

    def _create_handles(self) -> None:
        positions = ["nw", "ne", "se", "sw"]
        for key in positions:
            handle = ResizeHandleItem(key, self)
            handle.setVisible(False)
            self.handles[key] = handle

    def _update_handle_positions(self) -> None:
        rect = self.boundingRect()
        if "nw" in self.handles:
            self.handles["nw"].setPos(rect.left(), rect.top())
        if "ne" in self.handles:
            self.handles["ne"].setPos(rect.right(), rect.top())
        if "se" in self.handles:
            self.handles["se"].setPos(rect.right(), rect.bottom())
        if "sw" in self.handles:
            self.handles["sw"].setPos(rect.left(), rect.bottom())

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            is_sel = bool(value)
            for handle in self.handles.values():
                handle.setVisible(is_sel)
            self.update()
        return super().itemChange(change, value)

    def update_from_element(self) -> None:
        self.setPos(self.element.x, self.element.y)
        self.setRotation(self.element.rotation)
        self._update_handle_positions()

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

    def paint_selection_outline(self, painter: QPainter) -> None:
        """Draw dashed bounding box outline when item is selected or moved."""
        if self.isSelected():
            painter.save()
            outline_pen = QPen(QColor("#0078D4"))
            outline_pen.setStyle(Qt.DashLine)
            outline_pen.setWidthF(1.5)
            painter.setPen(outline_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())
            painter.restore()
