"""Tools that create an element by dragging: line, rectangle and ellipse."""
from abc import abstractmethod
from typing import override

from PySide6.QtCore import QPointF, Qt

from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool
from pandaplot.models.project.items.sketch import EllipseElement, LineElement, RectangleElement, SketchElement


class DragShapeTool(BaseTool):
    """Press at one point, drag to another, release to create the shape.

    A drag shorter than the canvas's minimum drag distance (a click) creates
    nothing.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._start: QPointF | None = None

    @abstractmethod
    def _element(self, start: QPointF, end: QPointF) -> SketchElement:
        """The element spanning `start` to `end`."""

    def _big_enough(self, start: QPointF, end: QPointF) -> bool:
        minimum = self.canvas.min_drag_distance()
        return abs(end.x() - start.x()) >= minimum and abs(end.y() - start.y()) >= minimum

    @override
    def press(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        if self.manager.report_if_drawing_blocked():
            return
        self._start = pos

    @override
    def move(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        if self._start is not None:
            self.canvas.show_preview(self._element(self._start, pos))

    @override
    def release(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        start, self._start = self._start, None
        self.canvas.show_preview(None)
        if start is not None and self._big_enough(start, pos):
            self.manager.add_element(self._element(start, pos))

    @override
    def cancel(self) -> bool:
        was_drawing = self._start is not None
        self._start = None
        self.canvas.show_preview(None)
        return was_drawing


class LineTool(DragShapeTool):
    """Drag from the line's start to its end."""

    @override
    def _element(self, start: QPointF, end: QPointF) -> SketchElement:
        return LineElement(x=start.x(), y=start.y(), dx=end.x() - start.x(), dy=end.y() - start.y(), **self.manager.style.shape_kwargs())

    @override
    def _big_enough(self, start: QPointF, end: QPointF) -> bool:
        # A line only needs length, not width and height.
        minimum = self.canvas.min_drag_distance()
        return abs(end.x() - start.x()) >= minimum or abs(end.y() - start.y()) >= minimum


class RectangleTool(DragShapeTool):
    """Drag from one corner to the opposite one."""

    @override
    def _element(self, start: QPointF, end: QPointF) -> SketchElement:
        return RectangleElement(
            x=min(start.x(), end.x()), y=min(start.y(), end.y()),
            width=abs(end.x() - start.x()), height=abs(end.y() - start.y()),
            **self.manager.style.shape_kwargs(),
        )


class EllipseTool(DragShapeTool):
    """Drag out the box the ellipse fits in, corner to corner."""

    @override
    def _element(self, start: QPointF, end: QPointF) -> SketchElement:
        return EllipseElement(
            x=(start.x() + end.x()) / 2, y=(start.y() + end.y()) / 2,
            rx=abs(end.x() - start.x()) / 2, ry=abs(end.y() - start.y()) / 2,
            **self.manager.style.shape_kwargs(),
        )
