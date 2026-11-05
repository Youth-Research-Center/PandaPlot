"""Builds the QGraphicsItem that draws each sketch element.

Each item is placed at its element's anchor (`setPos(x, y)`) and rotated
around it, so the item's local coordinates are the element's relative
geometry. Items carry their element id under `ELEMENT_ID_KEY`.
"""
import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen, QTextOption
from PySide6.QtWidgets import (
    QAbstractGraphicsShapeItem,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsTextItem,
)

from pandaplot.models.project.items.sketch import (
    EllipseElement,
    FreehandElement,
    LineElement,
    RectangleElement,
    SketchElement,
    StrokeStyle,
    TextAlignment,
    TextElement,
)
from pandaplot.models.project.items.sketch.curves import smooth_segments

logger = logging.getLogger(__name__)

ELEMENT_ID_KEY = 0

PEN_STYLES: dict[StrokeStyle, Qt.PenStyle] = {
    StrokeStyle.SOLID: Qt.PenStyle.SolidLine,
    StrokeStyle.DASHED: Qt.PenStyle.DashLine,
    StrokeStyle.DOTTED: Qt.PenStyle.DotLine,
    StrokeStyle.DASH_DOT: Qt.PenStyle.DashDotLine,
}

TEXT_ALIGNMENTS: dict[TextAlignment, Qt.AlignmentFlag] = {
    TextAlignment.LEFT: Qt.AlignmentFlag.AlignLeft,
    TextAlignment.CENTER: Qt.AlignmentFlag.AlignHCenter,
    TextAlignment.RIGHT: Qt.AlignmentFlag.AlignRight,
}


def _color(value: str, fallback: Qt.GlobalColor) -> QColor:
    color = QColor(value)
    return color if color.isValid() else QColor(fallback)


def make_pen(element: SketchElement) -> QPen:
    """The stroke of `element`; a zero width draws no outline."""
    if element.stroke_width <= 0:
        return QPen(Qt.PenStyle.NoPen)
    pen = QPen(_color(element.stroke_color, Qt.GlobalColor.black), element.stroke_width, PEN_STYLES[element.stroke_style])
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def make_brush(element: SketchElement) -> QBrush:
    """The fill of `element`; no fill colour means no brush."""
    if element.fill_color is None:
        return QBrush(Qt.BrushStyle.NoBrush)
    return QBrush(_color(element.fill_color, Qt.GlobalColor.transparent))


def _styled(item: QAbstractGraphicsShapeItem, element: SketchElement) -> QAbstractGraphicsShapeItem:
    item.setPen(make_pen(element))
    item.setBrush(make_brush(element))
    return item


def smooth_path(points: list[tuple[float, float]]) -> QPainterPath:
    """The smooth curve through `points` (see `curves.smooth_segments()`)."""
    path = QPainterPath()
    if points:
        path.moveTo(*points[0])
        for (c1x, c1y), (c2x, c2y), (x, y) in smooth_segments(points):
            path.cubicTo(c1x, c1y, c2x, c2y, x, y)
    return path


def _build_freehand(element: FreehandElement) -> QGraphicsItem:
    return _styled(QGraphicsPathItem(smooth_path(element.points)), element)


def _build_line(element: LineElement) -> QGraphicsItem:
    item = QGraphicsLineItem(0.0, 0.0, element.dx, element.dy)
    item.setPen(make_pen(element))
    return item


def _build_rectangle(element: RectangleElement) -> QGraphicsItem:
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.0, 0.0, element.width, element.height), element.corner_radius, element.corner_radius)
    return _styled(QGraphicsPathItem(path), element)


def _build_ellipse(element: EllipseElement) -> QGraphicsItem:
    return _styled(QGraphicsEllipseItem(-element.rx, -element.ry, 2 * element.rx, 2 * element.ry), element)


def _build_text(element: TextElement) -> QGraphicsItem:
    item = QGraphicsTextItem()
    font = QFont(element.font_family)
    # Pixel size, not point size: canvas units must lay out the same on
    # every platform, whatever its logical DPI.
    font.setPixelSize(element.font_size)
    font.setBold(element.is_bold)
    font.setItalic(element.is_italic)
    item.setFont(font)
    item.setDefaultTextColor(_color(element.stroke_color, Qt.GlobalColor.black))
    item.setPlainText(element.text)
    document = item.document()
    document.setDefaultTextOption(QTextOption(TEXT_ALIGNMENTS[element.alignment]))
    # Alignment only applies within a fixed text width; use the widest line.
    item.setTextWidth(document.idealWidth())
    return item


# Element class -> builder. A new element type adds its builder here, next
# to its entry in ELEMENT_TYPES.
GRAPHICS_ITEM_BUILDERS: dict[type[SketchElement], Callable[[Any], QGraphicsItem]] = {
    FreehandElement: _build_freehand,
    LineElement: _build_line,
    RectangleElement: _build_rectangle,
    EllipseElement: _build_ellipse,
    TextElement: _build_text,
}


def build_graphics_item(element: SketchElement) -> QGraphicsItem | None:
    """Create the item that draws `element`.

    Args:
        element: The element to draw.

    Returns:
        The positioned and rotated item, or None if no builder is
        registered for the element's type.
    """
    builder = GRAPHICS_ITEM_BUILDERS.get(type(element))
    if builder is None:
        logger.warning("No graphics item builder for sketch element type %s", type(element).__name__)
        return None
    item = builder(element)
    item.setPos(element.x, element.y)
    item.setRotation(element.rotation)
    item.setData(ELEMENT_ID_KEY, element.id)
    return item
