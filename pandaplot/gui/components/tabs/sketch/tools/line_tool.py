from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QGraphicsItem

from pandaplot.gui.components.tabs.sketch.graphics_items import create_graphics_item_for_element
from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool, ToolMode
from pandaplot.models.project.items.sketch import LineElement

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


class LineTool(BaseTool):
    """Tool for drawing straight lines with live preview."""

    def __init__(self, canvas: "SketchCanvas"):
        super().__init__(ToolMode.LINE, canvas)
        self.start_pos: Optional[tuple[float, float]] = None
        self.preview_item: Optional[QGraphicsItem] = None

    def mouse_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            layer = self.canvas.sketch.get_active_layer()
            if not layer or not layer.visible or layer.locked:
                return
            pos = self.canvas.mapToScene(event.position().toPoint())
            self.start_pos = (pos.x(), pos.y())

    def mouse_move(self, event: QMouseEvent) -> None:
        if self.start_pos is not None:
            end_pos = self.canvas.mapToScene(event.position().toPoint())
            if self.preview_item:
                self.canvas.scene().removeItem(self.preview_item)
                self.preview_item = None

            temp_elem = LineElement(
                x1=self.start_pos[0],
                y1=self.start_pos[1],
                x2=end_pos.x(),
                y2=end_pos.y(),
                stroke_color=self.canvas.active_stroke_color,
                stroke_width=self.canvas.active_stroke_width,
                stroke_style=self.canvas.active_stroke_style,
            )
            self.preview_item = create_graphics_item_for_element(temp_elem)
            if self.preview_item:
                self.canvas.scene().addItem(self.preview_item)

    def mouse_release(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self.start_pos is not None:
            if self.preview_item:
                self.canvas.scene().removeItem(self.preview_item)
                self.preview_item = None

            end_pos = self.canvas.mapToScene(event.position().toPoint())
            x1, y1 = self.start_pos
            x2, y2 = end_pos.x(), end_pos.y()
            if abs(x2 - x1) > 2 or abs(y2 - y1) > 2:
                elem = LineElement(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    stroke_color=self.canvas.active_stroke_color,
                    stroke_width=self.canvas.active_stroke_width,
                    stroke_style=self.canvas.active_stroke_style,
                )
                self.canvas.add_element_to_active_layer(elem)
            self.start_pos = None
