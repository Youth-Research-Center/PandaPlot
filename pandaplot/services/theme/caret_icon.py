"""Downward caret image for styled combo boxes.

Styling a combo box's ``::drop-down`` removes Qt's native arrow, and a Qt
stylesheet can only point ``::down-arrow`` at an image URL, so the caret is
rendered on demand in the colour the theme asks for.
"""
from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF

_CARET_SIZE = 12


def caret_icon_path(color_hex: str) -> str:
    """Return a filesystem path to a downward-caret PNG in ``color_hex``.

    The image is generated on first use and cached in the temp directory.
    It is drawn into a ``QImage`` rather than a ``QPixmap`` so it can be built
    before a ``QGuiApplication`` exists, as when a stylesheet is built in a
    test or at start-up.

    Args:
        color_hex: Fill colour of the caret, e.g. ``"#6B7280"``.

    Returns:
        The PNG path with forward slashes, ready to embed in ``url(...)``.
    """
    key = color_hex.lstrip("#")
    path = os.path.join(tempfile.gettempdir(), f"pandaplot_caret_{key}.png")
    if not os.path.exists(path):
        image = QImage(_CARET_SIZE, _CARET_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color_hex))
        painter.drawPolygon(QPolygonF([QPointF(2.5, 4.5), QPointF(9.5, 4.5), QPointF(6.0, 8.5)]))
        painter.end()
        image.save(path)
    return path.replace(os.sep, "/")
