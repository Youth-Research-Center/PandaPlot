from typing import TYPE_CHECKING, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent

from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool, ToolMode
from pandaplot.models.project.items.sketch import FreehandElement

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


class FreehandTool(BaseTool):
    """Tool for freehand stroke drawing."""

    def __init__(self, canvas: "SketchCanvas"):
        super().__init__(ToolMode.FREEHAND, canvas)
        self.is_drawing: bool = False
        self.current_points: List[Tuple[float, float]] = []

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

    def mouse_release(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self.is_drawing:
            self.is_drawing = False
            if len(self.current_points) > 1:
                elem = FreehandElement(
                    points=self.current_points,
                    stroke_color=self.canvas.active_stroke_color,
                    stroke_width=self.canvas.active_stroke_width,
                    stroke_style=self.canvas.active_stroke_style,
                )
                self.canvas.add_element_to_active_layer(elem)
            self.current_points = []
