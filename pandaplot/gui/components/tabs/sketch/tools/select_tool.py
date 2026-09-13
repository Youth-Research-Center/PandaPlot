from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from pandaplot.commands.composite_command import CompositeCommand
from pandaplot.commands.project.sketch.sketch_commands import (
    TransformCircuitComponentCommand,
    UpdateWireWaypointsCommand,
)
from pandaplot.gui.components.tabs.sketch.graphics_items.base_graphics_item import BaseGraphicsItem
from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool, ToolMode
from pandaplot.gui.components.tabs.sketch.tools.wire_tool import get_attached_wire_updates
from pandaplot.models.project.items.sketch import CircuitComponentElement

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
            return

        selected_items = self.canvas.scene().selectedItems()
        circuit_items = [
            item for item in selected_items
            if isinstance(item, BaseGraphicsItem) and isinstance(item.element, CircuitComponentElement)
        ]

        if not circuit_items:
            return

        key = event.key()
        if key == Qt.Key_R:
            delta = -90.0 if (event.modifiers() & Qt.ShiftModifier) else 90.0
            self._transform_circuit_components(circuit_items, delta_rot=delta)
        elif key == Qt.Key_H:
            self._transform_circuit_components(circuit_items, toggle_h=True)
        elif key == Qt.Key_V:
            self._transform_circuit_components(circuit_items, toggle_v=True)

    def _transform_circuit_components(self, items, delta_rot=0.0, toggle_h=False, toggle_v=False):
        for item in items:
            elem = item.element
            new_rot = (elem.rotation + delta_rot) % 360.0
            new_h = not elem.flip_horizontal if toggle_h else elem.flip_horizontal
            new_v = not elem.flip_vertical if toggle_v else elem.flip_vertical

            t_cmd = TransformCircuitComponentCommand(
                self.canvas.sketch,
                elem.id,
                rotation=new_rot,
                flip_horizontal=new_h,
                flip_vertical=new_v,
            )

            updates = get_attached_wire_updates(self.canvas.sketch, elem.id)
            wire_cmds = [
                UpdateWireWaypointsCommand(self.canvas.sketch, w_id, wps)
                for w_id, wps in updates
            ]

            if wire_cmds:
                comp = CompositeCommand([t_cmd] + wire_cmds)
            else:
                comp = t_cmd

            if self.canvas.command_executor:
                self.canvas.command_executor.execute_command(comp)
            else:
                comp.execute()

            item.update_from_element()
            item.update()

        self.canvas.notify_sketch_changed()
