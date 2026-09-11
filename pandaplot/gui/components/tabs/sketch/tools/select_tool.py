from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from pandaplot.gui.components.tabs.sketch.graphics_items.base_graphics_item import BaseGraphicsItem
from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool, ToolMode

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


class SelectTool(BaseTool):
    """Tool for selecting, dragging, and manipulating canvas elements."""

    def __init__(self, canvas: "SketchCanvas"):
        super().__init__(ToolMode.SELECT, canvas)

    def mouse_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            scene_pos = self.canvas.mapToScene(event.position().toPoint())
            item = self.canvas.scene().itemAt(scene_pos, self.canvas.transform())
            if isinstance(item, BaseGraphicsItem):
                if not (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                    if not item.isSelected():
                        self.canvas.scene().clearSelection()
                        item.setSelected(True)
                else:
                    item.setSelected(not item.isSelected())

    def mouse_release(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            for item in self.canvas.scene().selectedItems():
                if isinstance(item, BaseGraphicsItem):
                    item.sync_to_element()
            self.canvas.notify_sketch_changed()

    def key_press(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.canvas.delete_selected_elements()
