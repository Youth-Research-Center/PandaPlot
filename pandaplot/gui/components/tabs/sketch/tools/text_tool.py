from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QInputDialog

from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool, ToolMode
from pandaplot.models.project.items.sketch import TextElement

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


class TextTool(BaseTool):
    """Tool for inserting text labels onto the canvas."""

    def __init__(self, canvas: "SketchCanvas"):
        super().__init__(ToolMode.TEXT, canvas)

    def mouse_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            layer = self.canvas.sketch.get_active_layer()
            if not layer or not layer.visible or layer.locked:
                return
            pos = self.canvas.mapToScene(event.position().toPoint())
            text, ok = QInputDialog.getText(self.canvas, "Add Text", "Enter text:")
            if ok and text:
                elem = TextElement(
                    x=pos.x(),
                    y=pos.y(),
                    text=text,
                    font_family=self.canvas.active_font_family,
                    font_size=self.canvas.active_font_size,
                    is_bold=self.canvas.active_font_bold,
                    is_italic=self.canvas.active_font_italic,
                    alignment=self.canvas.active_text_alignment,
                    stroke_color=self.canvas.active_stroke_color,
                )
                self.canvas.add_element_to_active_layer(elem)
