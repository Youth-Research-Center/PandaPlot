from typing import Dict, List, Optional

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QKeyEvent, QMouseEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.composite_command import CompositeCommand
from pandaplot.commands.project.sketch import (
    AddSketchElementCommand,
    DeleteSketchElementsCommand,
    UpdateSketchElementStyleCommand,
)
from pandaplot.gui.components.tabs.sketch.graphics_items import (
    BaseGraphicsItem,
    create_graphics_item_for_element,
)
from pandaplot.gui.components.tabs.sketch.tools.tool_manager import ToolManager
from pandaplot.models.project.items.sketch import Sketch, SketchElement


class SketchCanvas(QGraphicsView):
    """Interactive canvas QGraphicsView wrapper for a Sketch item."""

    sketch_changed = Signal()
    selection_changed = Signal()

    def __init__(
        self,
        sketch: Sketch,
        command_executor: Optional[CommandExecutor] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self.sketch: Sketch = sketch
        self.command_executor: Optional[CommandExecutor] = command_executor
        self.tool_manager = ToolManager(self)

        self.item_map: Dict[str, BaseGraphicsItem] = {}

        self.active_stroke_color: str = "#000000"
        self.active_stroke_width: float = 2.0
        self.active_stroke_style: str = "solid"
        self.active_fill_color: str = "none"
        self.active_font_family: str = "Sans-Serif"
        self.active_font_size: int = 14

        self.is_panning: bool = False
        self.pan_start: QPointF = QPointF()

        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        self.scene().selectionChanged.connect(self.selection_changed.emit)

        self.rebuild_scene()

    def rebuild_scene(self) -> None:
        """Rebuild all scene items from sketch model layers, preserving selection."""
        selected_ids = {
            item.element.id
            for item in self.scene().selectedItems()
            if isinstance(item, BaseGraphicsItem)
        }

        self.scene().clear()
        self.item_map.clear()

        bg_color = QColor(self.sketch.background_color)
        self.scene().setBackgroundBrush(QBrush(bg_color))
        self.scene().setSceneRect(0, 0, self.sketch.canvas_width, self.sketch.canvas_height)

        for z_idx, layer in enumerate(self.sketch.layers):
            if not layer.visible:
                continue
            for elem in layer.elements:
                item = create_graphics_item_for_element(elem)
                if item:
                    item.setZValue(z_idx)
                    item.setOpacity(layer.opacity)
                    if layer.locked:
                        item.setFlag(BaseGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                        item.setFlag(BaseGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                    self.scene().addItem(item)
                    self.item_map[elem.id] = item
                    if elem.id in selected_ids and not layer.locked:
                        item.setSelected(True)

    def add_element_to_active_layer(self, element: SketchElement) -> None:
        """Add an element to the active layer in model and scene via command if available."""
        layer = self.sketch.get_active_layer()
        if not layer or layer.locked or not layer.visible:
            return

        if self.command_executor:
            cmd = AddSketchElementCommand(self.sketch, layer.id, element)
            self.command_executor.execute_command(cmd)
        else:
            layer.elements.append(element)

        self.rebuild_scene()
        self.sketch_changed.emit()

    def delete_selected_elements(self) -> None:
        """Delete currently selected elements across unlocked layers via command if available."""
        selected_items = self.scene().selectedItems()
        if not selected_items:
            return

        layer_elem_map: Dict[str, List[str]] = {}
        for item in selected_items:
            if isinstance(item, BaseGraphicsItem):
                elem_id = item.element.id
                for layer in self.sketch.layers:
                    if not layer.locked and any(e.id == elem_id for e in layer.elements):
                        layer_elem_map.setdefault(layer.id, []).append(elem_id)
                        break

        if not layer_elem_map:
            return

        if self.command_executor:
            commands = [
                DeleteSketchElementsCommand(self.sketch, lid, elem_ids)
                for lid, elem_ids in layer_elem_map.items()
            ]
            if len(commands) == 1:
                self.command_executor.execute_command(commands[0])
            else:
                self.command_executor.execute_command(CompositeCommand(commands))
        else:
            for lid, elem_ids in layer_elem_map.items():
                layer = self.sketch.get_layer(lid)
                if layer:
                    id_set = set(elem_ids)
                    layer.elements = [e for e in layer.elements if e.id not in id_set]

        self.rebuild_scene()
        self.sketch_changed.emit()

    def apply_style_change_to_selection(self, property_dict: dict) -> None:
        """Apply style property changes to selected elements."""
        selected_items = self.scene().selectedItems()
        if not selected_items:
            return

        selected_ids = [
            item.element.id for item in selected_items if isinstance(item, BaseGraphicsItem)
        ]
        if not selected_ids:
            return

        if self.command_executor:
            cmd = UpdateSketchElementStyleCommand(self.sketch, selected_ids, property_dict)
            self.command_executor.execute_command(cmd)
        else:
            for layer in self.sketch.layers:
                for elem in layer.elements:
                    if elem.id in set(selected_ids):
                        for k, v in property_dict.items():
                            if hasattr(elem, k):
                                setattr(elem, k, v)

        self.rebuild_scene()
        self.sketch_changed.emit()

    def notify_sketch_changed(self) -> None:
        self.sketch_changed.emit()

    # Viewport Navigation & Mouse/Key Event Handlers
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton or (
            event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier
        ):
            self.is_panning = True
            self.pan_start = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        self.tool_manager.mouse_press(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.is_panning:
            delta = event.position() - self.pan_start
            self.pan_start = event.position()
            self.horizontalScrollBar().setValue(
                int(self.horizontalScrollBar().value() - delta.x())
            )
            self.verticalScrollBar().setValue(
                int(self.verticalScrollBar().value() - delta.y())
            )
            event.accept()
            return

        self.tool_manager.mouse_move(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.is_panning and (
            event.button() == Qt.MiddleButton or event.button() == Qt.LeftButton
        ):
            self.is_panning = False
            self.unsetCursor()
            event.accept()
            return

        self.tool_manager.mouse_release(event)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.ControlModifier:
            zoom_factor = 1.15 if event.angleDelta().y() > 0 else 0.85
            self.scale(zoom_factor, zoom_factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self.tool_manager.key_press(event)
        super().keyPressEvent(event)
