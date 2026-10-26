"""Pen tool: draws a smooth freehand stroke."""
import math
from typing import override

from PySide6.QtCore import QPointF, Qt

from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool
from pandaplot.models.project.items.sketch import FreehandElement
from pandaplot.models.project.items.sketch.curves import Point, simplify


class FreehandTool(BaseTool):
    """Press and drag to draw; the stroke becomes a smooth curve.

    The pointer path is simplified to the fewest points that stay within
    SIMPLIFY_TOLERANCE_PX screen pixels of it, and the curve is drawn
    through those, so the stroke looks the same at any zoom and stores few
    points. A press without a drag draws nothing.
    """

    SIMPLIFY_TOLERANCE_PX = 1.5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._points: list[Point] = []

    def _stroke(self) -> FreehandElement | None:
        points = simplify(self._points, self.SIMPLIFY_TOLERANCE_PX / self.canvas.zoom)
        if len(points) < 2:
            return None
        x0, y0 = points[0]
        return FreehandElement(x=x0, y=y0, points=[(x - x0, y - y0) for x, y in points], **self.manager.style.shape_kwargs())

    @override
    def press(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        if self.manager.report_if_drawing_blocked():
            return
        self._points = [(pos.x(), pos.y())]

    @override
    def move(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        if not self._points:
            return
        last_x, last_y = self._points[-1]
        # Ignore pointer jitter smaller than a screen pixel.
        if math.hypot(pos.x() - last_x, pos.y() - last_y) * self.canvas.zoom < 1.0:
            return
        self._points.append((pos.x(), pos.y()))
        self.canvas.show_preview(self._stroke())

    @override
    def release(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        if not self._points:
            return
        self.move(pos, modifiers)
        stroke = self._stroke()
        self._points = []
        self.canvas.show_preview(None)
        if stroke is not None:
            self.manager.add_element(stroke)

    @override
    def cancel(self) -> bool:
        was_drawing = bool(self._points)
        self._points = []
        self.canvas.show_preview(None)
        return was_drawing
