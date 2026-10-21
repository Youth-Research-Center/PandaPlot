"""Selection tool: select, move, resize and delete elements."""
import dataclasses
from enum import Enum, auto
from typing import Any, override

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QKeyEvent

from pandaplot.commands.project.sketch import DeleteSketchElementsCommand, TransformSketchElementsCommand
from pandaplot.gui.components.tabs.sketch.geometry import Handle, move_changes, resized_box, scale_changes
from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool
from pandaplot.models.project.items.sketch import SketchElement


class _Gesture(Enum):
    IDLE = auto()
    PRESSED = auto()  # on a selected element; becomes MOVING once dragged far enough
    MOVING = auto()
    RESIZING = auto()
    RUBBER_BAND = auto()


class SelectTool(BaseTool):
    """Click to select (Shift-click adds or removes), drag on empty canvas to
    select everything the box touches, drag the selection to move it, drag a
    handle to resize it (Shift on a corner keeps the proportions), and press
    Delete or Backspace to delete it.

    Only elements on visible, unlocked layers can be picked. A move or
    resize is previewed while dragging and committed on release as one
    TransformSketchElementsCommand.
    """

    cursor = Qt.CursorShape.ArrowCursor

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._gesture = _Gesture.IDLE
        self._press_pos = QPointF()
        self._originals: dict[str, SketchElement] = {}
        self._handle: Handle | None = None
        self._box = QRectF()
        self._base_selection: list[str] = []

    def _capture_originals(self) -> None:
        self._originals = {}
        for element_id in self.canvas.selected_ids:
            found = self.canvas.sketch.find_element(element_id)
            if found is not None:
                self._originals[element_id] = found[1]

    def _changes(self, gesture: _Gesture, pos: QPointF, modifiers: Qt.KeyboardModifier) -> dict[str, dict[str, Any]]:
        """Geometry changes of a move or resize gesture with the pointer at `pos`."""
        if gesture is _Gesture.MOVING:
            dx, dy = pos.x() - self._press_pos.x(), pos.y() - self._press_pos.y()
            return {element_id: move_changes(element, dx, dy) for element_id, element in self._originals.items()}
        assert self._handle is not None
        keep_aspect = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        new_box = resized_box(self._box, self._handle, pos, keep_aspect=keep_aspect, min_size=self.canvas.min_drag_distance())
        return {element_id: scale_changes(element, self._box, new_box) for element_id, element in self._originals.items()}

    def _preview(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        changes = self._changes(self._gesture, pos, modifiers)
        self.canvas.preview_elements({
            element_id: dataclasses.replace(self._originals[element_id], **element_changes)
            for element_id, element_changes in changes.items()
        })

    @override
    def press(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        self._press_pos = pos
        handle = self.canvas.handle_at(pos)
        if handle is not None:
            box = self.canvas.selection_rect()
            if box is not None:
                self._gesture, self._handle, self._box = _Gesture.RESIZING, handle, box
                self._capture_originals()
                return
        add_or_remove = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        selection = list(self.canvas.selected_ids)
        hit = self.canvas.element_at(pos)
        if hit is None:
            self._base_selection = selection if add_or_remove else []
            if not add_or_remove:
                self.canvas.clear_selection()
            self._gesture = _Gesture.RUBBER_BAND
            return
        if add_or_remove and hit in selection:
            self.canvas.set_selection([element_id for element_id in selection if element_id != hit])
            self._gesture = _Gesture.IDLE
            return
        if hit not in selection:
            self.canvas.set_selection([*selection, hit] if add_or_remove else [hit])
        self._capture_originals()
        self._gesture = _Gesture.PRESSED

    @override
    def move(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        if self._gesture is _Gesture.PRESSED:
            dragged = max(abs(pos.x() - self._press_pos.x()), abs(pos.y() - self._press_pos.y()))
            if dragged < self.canvas.min_drag_distance():
                return
            self._gesture = _Gesture.MOVING
        if self._gesture in (_Gesture.MOVING, _Gesture.RESIZING):
            self._preview(pos, modifiers)
        elif self._gesture is _Gesture.RUBBER_BAND:
            self.canvas.show_rubber_band(QRectF(self._press_pos, pos))

    @override
    def release(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        gesture, self._gesture = self._gesture, _Gesture.IDLE
        if gesture in (_Gesture.MOVING, _Gesture.RESIZING):
            command = TransformSketchElementsCommand(self.manager.app_context, self.canvas.sketch, self._changes(gesture, pos, modifiers))
            self._originals = {}
            # A successful command redraws the canvas through sketch.changed;
            # otherwise put back what the preview moved.
            if not self.manager.execute(command):
                self.canvas.rebuild()
        elif gesture is _Gesture.RUBBER_BAND:
            self.canvas.show_rubber_band(None)
            rect = QRectF(self._press_pos, pos).normalized()
            minimum = self.canvas.min_drag_distance()
            if rect.width() >= minimum or rect.height() >= minimum:
                self.canvas.set_selection([*self._base_selection, *self.canvas.elements_in(rect)])
        self._originals = {}

    @override
    def key_press(self, event: QKeyEvent) -> bool:
        if event.key() not in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) or not self.canvas.selected_ids:
            return False
        if self._gesture is not _Gesture.IDLE:
            self.cancel()
        self.manager.execute(DeleteSketchElementsCommand(self.manager.app_context, self.canvas.sketch, list(self.canvas.selected_ids)))
        return True

    @override
    def cancel(self) -> bool:
        gesture, self._gesture = self._gesture, _Gesture.IDLE
        self._originals = {}
        if gesture in (_Gesture.MOVING, _Gesture.RESIZING):
            self.canvas.rebuild()
        elif gesture is _Gesture.RUBBER_BAND:
            self.canvas.show_rubber_band(None)
            self.canvas.set_selection(self._base_selection)
        return gesture is not _Gesture.IDLE
