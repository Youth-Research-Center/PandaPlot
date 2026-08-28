"""Small line-drawn icons for the chart-type list on the wizard's Type step.

Drawn with QPainter primitives (no SVG/asset files) so there's nothing to
ship or theme separately -- `color` is passed in by the caller (typically the
current design token's `accent` or `text_secondary`) each time the theme
changes.
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPen, QPixmap


def _paint_line(painter: QPainter, size: int):
    points = [QPointF(1, size - 3), QPointF(size * 0.4, size * 0.45),
              QPointF(size * 0.65, size * 0.65), QPointF(size - 1, 2)]
    painter.drawPolyline(points)


def _paint_scatter(painter: QPainter, size: int):
    painter.setBrush(painter.pen().color())
    for x, y in ((size * 0.25, size * 0.7), (size * 0.5, size * 0.35), (size * 0.75, size * 0.55)):
        painter.drawEllipse(QRectF(x - 1.5, y - 1.5, 3, 3))


def _paint_bar(painter: QPainter, size: int):
    bars = [(1, size * 0.5, 3, size * 0.4), (size * 0.4, size * 0.25, 3, size * 0.65),
            (size * 0.7, size * 0.4, 3, size * 0.5)]
    for x, y, w, h in bars:
        painter.drawRect(QRectF(x, y, w, h))


def _paint_hist(painter: QPainter, size: int):
    bars = [(1, size * 0.65, 3, size * 0.25), (size * 0.35, size * 0.3, 3, size * 0.6),
            (size * 0.65, size * 0.5, 3, size * 0.4)]
    for x, y, w, h in bars:
        painter.drawRect(QRectF(x, y, w, h))


def _vector_arrow_geometry(size: int):
    """Compute the (start, end, [wing1, wing2]) points for each arrow.

    Pulled out of `_paint_vector` so tests can assert the geometry stays
    within the [0, size] icon canvas without needing to inspect pixels.
    """
    arrows = []
    for start_frac, end_frac in (
        ((0.15, 0.85), (0.55, 0.35)),
        ((0.35, 0.9), (0.8, 0.3)),
    ):
        start = QPointF(size * start_frac[0], size * start_frac[1])
        end = QPointF(size * end_frac[0], size * end_frac[1])
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        head_len = size * 0.2
        wings = []
        for delta in (2.6, -2.6):
            wings.append(QPointF(
                end.x() - head_len * math.cos(angle + delta),
                end.y() - head_len * math.sin(angle + delta),
            ))
        arrows.append((start, end, wings))
    return arrows


def _paint_vector(painter: QPainter, size: int):
    for start, end, wings in _vector_arrow_geometry(size):
        painter.drawLine(start, end)
        for head_point in wings:
            painter.drawLine(end, head_point)


def _paint_colormap(painter: QPainter, size: int):
    painter.setBrush(painter.pen().color())
    for x, y in ((size * 0.25, size * 0.7), (size * 0.5, size * 0.35), (size * 0.75, size * 0.55)):
        painter.drawEllipse(QRectF(x - 2, y - 2, 4, 4))


def _paint_heatmap(painter: QPainter, size: int):
    cell = size / 3
    for row in range(3):
        for col in range(3):
            painter.drawRect(QRectF(col * cell, row * cell, cell, cell))


def _cube_edges(size: int):
    """The nine visible edges of a wireframe cube, as (start, end) point
    pairs -- the shared skeleton every 3-D icon is drawn on or inside.

    Pulled out (like `_vector_arrow_geometry`) so tests can assert the
    geometry stays inside the [0, size] icon canvas without inspecting
    pixels. The cube is an isometric-ish box: a front face, a back face
    offset up-and-right by `depth`, and the three connecting edges that
    would be visible from that angle.
    """
    depth = size * 0.22
    left, right = size * 0.12, size * 0.66
    top, bottom = size * 0.3, size * 0.86
    front = [(left, top), (right, top), (right, bottom), (left, bottom)]
    back = [(x + depth, y - depth) for x, y in front]
    edges = []
    for corners in (front, back):
        for index in range(4):
            edges.append((QPointF(*corners[index]), QPointF(*corners[(index + 1) % 4])))
    # Only the top-right connector reads at this size; drawing all four
    # turns a 14px icon into a smudge.
    edges.append((QPointF(*front[1]), QPointF(*back[1])))
    return edges


def _paint_axes3d(painter: QPainter, size: int):
    """The three-axis corner every 3-D icon shares, so the whole family
    reads as "3-D" at a glance before the per-type mark is drawn."""
    origin = QPointF(size * 0.2, size * 0.8)
    for end in (QPointF(size * 0.2, size * 0.15),
                QPointF(size * 0.9, size * 0.8),
                QPointF(size * 0.55, size * 0.95)):
        painter.drawLine(origin, end)


def _paint_scatter3d(painter: QPainter, size: int):
    _paint_axes3d(painter, size)
    painter.setBrush(painter.pen().color())
    for x, y in ((size * 0.4, size * 0.6), (size * 0.6, size * 0.4), (size * 0.75, size * 0.62)):
        painter.drawEllipse(QRectF(x - 1.5, y - 1.5, 3, 3))


def _paint_line3d(painter: QPainter, size: int):
    _paint_axes3d(painter, size)
    painter.drawPolyline([QPointF(size * 0.3, size * 0.7), QPointF(size * 0.45, size * 0.35),
                          QPointF(size * 0.65, size * 0.62), QPointF(size * 0.85, size * 0.3)])


def _paint_surface(painter: QPainter, size: int):
    """A filled quad reading as a sheet in perspective -- the same
    footprint as the wireframe icon, shaded rather than gridded, which is
    exactly the difference between the two chart types."""
    corners = [QPointF(size * 0.1, size * 0.62), QPointF(size * 0.45, size * 0.8),
               QPointF(size * 0.9, size * 0.5), QPointF(size * 0.5, size * 0.28)]
    painter.setBrush(painter.pen().color())
    painter.drawPolygon(corners)


def _paint_wireframe(painter: QPainter, size: int):
    for start, end in _cube_edges(size):
        painter.drawLine(start, end)


def _paint_bar3d(painter: QPainter, size: int):
    _paint_axes3d(painter, size)
    depth = size * 0.12
    for x, height in ((size * 0.32, size * 0.3), (size * 0.55, size * 0.5), (size * 0.75, size * 0.22)):
        base = size * 0.78
        painter.drawRect(QRectF(x, base - height, size * 0.12, height))
        painter.drawLine(QPointF(x, base - height), QPointF(x + depth, base - height - depth))
        painter.drawLine(QPointF(x + size * 0.12, base - height),
                         QPointF(x + size * 0.12 + depth, base - height - depth))
        painter.drawLine(QPointF(x + size * 0.12 + depth, base - height - depth),
                         QPointF(x + depth, base - height - depth))


def _paint_trisurf(painter: QPainter, size: int):
    """The same sheet as the surface icon, split into triangles -- the
    triangulation is the whole distinction between the two types."""
    corners = [QPointF(size * 0.1, size * 0.62), QPointF(size * 0.45, size * 0.82),
               QPointF(size * 0.9, size * 0.5), QPointF(size * 0.5, size * 0.26)]
    painter.drawPolygon(corners)
    painter.drawLine(corners[0], corners[2])
    painter.drawLine(corners[1], corners[3])


_PAINTERS = {
    "line": _paint_line,
    "scatter": _paint_scatter,
    "bar": _paint_bar,
    "hist": _paint_hist,
    "vector": _paint_vector,
    "colormap": _paint_colormap,
    "heatmap": _paint_heatmap,
    "scatter3d": _paint_scatter3d,
    "line3d": _paint_line3d,
    "surface": _paint_surface,
    "wireframe": _paint_wireframe,
    "bar3d": _paint_bar3d,
    "trisurf": _paint_trisurf,
}


def chart_type_icon(chart_type: str, color: str, size: int = 14) -> QIcon:
    """Render `chart_type`'s icon at `size`x`size` in `color`.

    Raises:
        KeyError: if `chart_type` isn't one of the registered chart types
        (the keys of `_PAINTERS`, which mirror `ChartType`).
    """
    paint_fn = _PAINTERS[chart_type]

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color)
    pen.setWidthF(1.5)
    painter.setPen(pen)
    paint_fn(painter, size)
    painter.end()
    return QIcon(pixmap)
