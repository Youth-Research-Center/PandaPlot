"""Hit-testing, bounds, moving and resizing of drawn sketch elements.

Positions are in scene (canvas) coordinates unless stated otherwise.
Element items are placed at their element's anchor and rotated around it,
so an item's local coordinates are the element's relative geometry.
"""
from collections.abc import Callable
from enum import Enum
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainterPath, QPainterPathStroker
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem, QGraphicsPathItem

from pandaplot.models.project.items.sketch import (
    EllipseElement,
    FreehandElement,
    LineElement,
    RectangleElement,
    SketchElement,
    TextElement,
)


class Handle(Enum):
    """A resize handle on the selection box, valued by its position as
    fractions (0, 0.5 or 1) of the box's width and height."""

    NW = (0.0, 0.0)
    N = (0.5, 0.0)
    NE = (1.0, 0.0)
    E = (1.0, 0.5)
    SE = (1.0, 1.0)
    S = (0.5, 1.0)
    SW = (0.0, 1.0)
    W = (0.0, 0.5)

    @property
    def is_corner(self) -> bool:
        return 0.5 not in self.value

    def position(self, box: QRectF) -> QPointF:
        fx, fy = self.value
        return QPointF(box.left() + fx * box.width(), box.top() + fy * box.height())


def _line_outline(item: QGraphicsLineItem) -> QPainterPath:
    path = QPainterPath(item.line().p1())
    path.lineTo(item.line().p2())
    return path


def _ellipse_outline(item: QGraphicsEllipseItem) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(item.rect())
    return path


# Item class -> its drawn outline in local coordinates. Text has none: it
# is hit and bounded by its whole text box.
_OUTLINES: dict[type[QGraphicsItem], Callable[[Any], QPainterPath]] = {
    QGraphicsPathItem: lambda item: item.path(),
    QGraphicsLineItem: _line_outline,
    QGraphicsEllipseItem: _ellipse_outline,
}


def shape_rect(item: QGraphicsItem) -> QRectF:
    """Scene bounds of what `item` draws, without the pen width, so moving
    and resizing line up with the element's geometry."""
    outline = _OUTLINES.get(type(item))
    local = outline(item).boundingRect() if outline is not None else item.boundingRect()
    return item.mapRectToScene(local)


def hits(element: SketchElement, item: QGraphicsItem, scene_pos: QPointF, tolerance: float) -> bool:
    """Whether a click at `scene_pos` lands on `element`.

    Strokes count within `tolerance` (or half their width, if wider), so a
    thin line is still easy to pick. A shape's inside counts only when it is
    filled, so an outline-only shape doesn't hide what lies inside it.
    """
    local = item.mapFromScene(scene_pos)
    outline = _OUTLINES.get(type(item))
    if outline is None:
        return item.boundingRect().adjusted(-tolerance, -tolerance, tolerance, tolerance).contains(local)
    path = outline(item)
    stroker = QPainterPathStroker()
    stroker.setWidth(max(element.stroke_width, 2 * tolerance))
    stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
    stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    if stroker.createStroke(path).contains(local):
        return True
    return element.fill_color is not None and path.contains(local)


def move_changes(element: SketchElement, dx: float, dy: float) -> dict[str, Any]:
    """Geometry changes that move `element` by (`dx`, `dy`)."""
    return {"x": element.x + dx, "y": element.y + dy}


def resized_box(box: QRectF, handle: Handle, pos: QPointF, *, keep_aspect: bool, min_size: float) -> QRectF:
    """The selection box after dragging `handle` to `pos`.

    The opposite side stays put and the box never flips or shrinks below
    `min_size`. An axis the box has no extent along (e.g. a horizontal
    line's height) is left unchanged. With `keep_aspect`, a corner handle
    scales both sides by the same factor.
    """
    left, top, right, bottom = box.left(), box.top(), box.right(), box.bottom()
    fx, fy = handle.value
    if box.width() > 0:
        if fx == 0.0:
            left = min(pos.x(), right - min_size)
        elif fx == 1.0:
            right = max(pos.x(), left + min_size)
    if box.height() > 0:
        if fy == 0.0:
            top = min(pos.y(), bottom - min_size)
        elif fy == 1.0:
            bottom = max(pos.y(), top + min_size)
    if keep_aspect and handle.is_corner and box.width() > 0 and box.height() > 0:
        sx, sy = (right - left) / box.width(), (bottom - top) / box.height()
        scale = sx if abs(sx - 1.0) >= abs(sy - 1.0) else sy
        scale = max(scale, min_size / box.width(), min_size / box.height())
        width, height = box.width() * scale, box.height() * scale
        if fx == 0.0:
            left = right - width
        else:
            right = left + width
        if fy == 0.0:
            top = bottom - height
        else:
            bottom = top + height
    return QRectF(QPointF(left, top), QPointF(right, bottom))


type _Scaler = Callable[[Any, float, float], dict[str, Any]]

# Element class -> its geometry changes for a scale of (sx, sy), applied
# about its anchor. The anchor itself is moved by scale_changes().
_SCALERS: dict[type[SketchElement], _Scaler] = {
    RectangleElement: lambda element, sx, sy: {
        "width": element.width * sx, "height": element.height * sy, "corner_radius": element.corner_radius * min(sx, sy),
    },
    EllipseElement: lambda element, sx, sy: {"rx": element.rx * sx, "ry": element.ry * sy},
    LineElement: lambda element, sx, sy: {"dx": element.dx * sx, "dy": element.dy * sy},
    FreehandElement: lambda element, sx, sy: {"points": [(px * sx, py * sy) for px, py in element.points]},
    # Text has no box of its own; it grows with its font size.
    TextElement: lambda element, _sx, sy: {"font_size": max(1, round(element.font_size * sy))},
}


def scale_changes(element: SketchElement, old_box: QRectF, new_box: QRectF) -> dict[str, Any]:
    """Geometry changes that map `element` from `old_box` onto `new_box`.

    Only meaningful for unrotated elements; the canvas hides the resize
    handles when a selected element is rotated.
    """
    sx = new_box.width() / old_box.width() if old_box.width() > 0 else 1.0
    sy = new_box.height() / old_box.height() if old_box.height() > 0 else 1.0
    changes = {
        "x": new_box.left() + (element.x - old_box.left()) * sx,
        "y": new_box.top() + (element.y - old_box.top()) * sy,
    }
    scaler = _SCALERS.get(type(element))
    if scaler is not None:
        changes.update(scaler(element, sx, sy))
    return changes
