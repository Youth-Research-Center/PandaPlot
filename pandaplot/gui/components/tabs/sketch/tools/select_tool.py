from typing import TYPE_CHECKING, Dict, Any, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from pandaplot.commands.project.sketch import MoveResizeSketchElementsCommand
from pandaplot.gui.components.tabs.sketch.graphics_items.base_graphics_item import BaseGraphicsItem
from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool, ToolMode

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


class SelectTool(BaseTool):
    """Tool for selecting, dragging, and manipulating canvas elements."""

    def __init__(self, canvas: "SketchCanvas"):
        super().__init__(ToolMode.SELECT, canvas)
        self.initial_states: Dict[str, Dict[str, Any]] = {}

    def _get_item_state(self, item: BaseGraphicsItem) -> Dict[str, Any]:
        elem = item.element
        state = {
            "x": item.pos().x(),
            "y": item.pos().y(),
            "rotation": item.rotation(),
        }
        if hasattr(elem, "width"):
            state["width"] = getattr(elem, "width")
        if hasattr(elem, "height"):
            state["height"] = getattr(elem, "height")
        if hasattr(elem, "rx"):
            state["rx"] = getattr(elem, "rx")
        if hasattr(elem, "ry"):
            state["ry"] = getattr(elem, "ry")
        if hasattr(elem, "x1"):
            state["x1"] = getattr(elem, "x1")
            state["y1"] = getattr(elem, "y1")
            state["x2"] = getattr(elem, "x2")
            state["y2"] = getattr(elem, "y2")
        return state

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

            self.initial_states = {}
            for sel_item in self.canvas.scene().selectedItems():
                if isinstance(sel_item, BaseGraphicsItem):
                    self.initial_states[sel_item.element.id] = self._get_item_state(sel_item)

    def mouse_release(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            new_states: Dict[str, Dict[str, Any]] = {}
            for item in self.canvas.scene().selectedItems():
                if isinstance(item, BaseGraphicsItem):
                    item.sync_to_element()
                    new_states[item.element.id] = self._get_item_state(item)

            if self.initial_states and new_states and self.initial_states != new_states:
                if self.canvas.command_executor:
                    cmd = MoveResizeSketchElementsCommand(
                        self.canvas.sketch,
                        self.initial_states,
                        new_states,
                        app_context=self.canvas.app_context,
                    )
                    self.canvas.command_executor.execute_command(cmd)

            self.initial_states = {}
            self.canvas.notify_sketch_changed()

    def key_press(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.canvas.delete_selected_elements()
