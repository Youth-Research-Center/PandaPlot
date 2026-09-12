from typing import TYPE_CHECKING, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QGraphicsItem

from pandaplot.gui.components.tabs.sketch.graphics_items import create_graphics_item_for_element
from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool, ToolMode
from pandaplot.models.project.items.sketch import FreehandElement

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


class FreehandTool(BaseTool):
    """Tool for live freehand stroke drawing."""

    def __init__(self, canvas: "SketchCanvas"):
        super().__init__(ToolMode.FREEHAND, canvas)
        self.is_drawing: bool = False
        self.current_points: List[Tuple[float, float]] = []
        self.preview_item: Optional[QGraphicsItem] = None

    def mouse_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            layer = self.canvas.sketch.get_active_layer()
            if not layer or not layer.visible or layer.locked:
                return
            self.is_drawing = True
            pos = self.canvas.mapToScene(event.position().toPoint())
            self.current_points = [(pos.x(), pos.y())]

    def mouse_move(self, event: QMouseEvent) -> None:
        if self.is_drawing:
            pos = self.canvas.mapToScene(event.position().toPoint())
            self.current_points.append((pos.x(), pos.y()))

            if self.preview_item:
                self.canvas.scene().removeItem(self.preview_item)
                self.preview_item = None

            if len(self.current_points) > 1:
                temp_elem = FreehandElement(
                    points=self.current_points,
                    stroke_color=self.canvas.active_stroke_color,
                    stroke_width=self.canvas.active_stroke_width,
                    stroke_style=self.canvas.active_stroke_style,
                )
                self.preview_item = create_graphics_item_for_element(temp_elem)
                if self.preview_item:
                    self.canvas.scene().addItem(self.preview_item)

    def mouse_release(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self.is_drawing:
            self.is_drawing = False
            if self.preview_item:
                self.canvas.scene().removeItem(self.preview_item)
                self.preview_item = None

            if len(self.current_points) > 1:
                elem = FreehandElement(
                    points=self.current_points,
                    stroke_color=self.canvas.active_stroke_color,
                    stroke_width=self.canvas.active_stroke_width,
                    stroke_style=self.canvas.active_stroke_style,
                )
                self.canvas.add_element_to_active_layer(elem)
            self.current_points = []
