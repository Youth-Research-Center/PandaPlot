"""
Shared gallery grid tile rendering: composes a base thumbnail/folder/broken
glyph plus an optional selection checkmark badge, all baked into one QIcon
from the current theme's design tokens.

Follows the same pattern as build_line_style_icon() (line_style_icons.py):
a pure function taking `tokens`, reused identically by the real
ImageGalleryTab grid and the pandaplot_storybook preview, so the two never
drift and the storybook can preview every combination without needing real
project data.
"""

from typing import Literal, Optional

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap

TileType = Literal["image", "album", "broken"]

_DEFAULT_SIZE = QSize(120, 120)
_BADGE_DIAMETER = 22
_BADGE_MARGIN = 6


def build_gallery_tile_icon(
    pixmap: Optional[QPixmap],
    tile_type: TileType,
    *,
    selected: bool,
    tokens: dict,
    size: QSize = _DEFAULT_SIZE,
) -> QIcon:
    """
    Build a themed gallery tile icon.

    `pixmap` is the already-decoded/scaled image thumbnail; ignored for
    "album"/"broken" tile_type (those draw a themed glyph instead). Set
    `selected=True` to composite a checkmark badge in the top-left
    corner.
    """
    canvas = QPixmap(size)
    canvas.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if tile_type == "image" and pixmap is not None:
        x = (size.width() - pixmap.width()) // 2
        y = (size.height() - pixmap.height()) // 2
        painter.drawPixmap(x, y, pixmap)
    elif tile_type == "album":
        _draw_folder_glyph(painter, size, tokens)
    else:  # "broken", or "image" with no pixmap (defensive fallback)
        _draw_broken_glyph(painter, size, tokens)

    if selected:
        _draw_selection_badge(painter, size, tokens)

    painter.end()
    return QIcon(canvas)


def _draw_folder_glyph(painter: QPainter, size: QSize, tokens: dict) -> None:
    """Simple filled folder shape, sized identically to image thumbnails
    (fixes v1's inconsistent QIcon.fromTheme("folder") sizing)."""
    fill = QColor(tokens.get("accent_selected_bg", "#EEF0FB"))
    outline = QColor(tokens.get("accent", "#4A56C6"))

    margin = size.width() * 0.12
    body_top = size.height() * 0.32
    tab_width = size.width() * 0.38

    painter.setBrush(QBrush(fill))
    painter.setPen(QPen(outline, 2))
    painter.drawRoundedRect(
        QRectF(margin, body_top, size.width() - 2 * margin, size.height() - body_top - margin),
        4, 4,
    )
    painter.drawRoundedRect(
        QRectF(margin, body_top - size.height() * 0.08, tab_width, size.height() * 0.1),
        3, 3,
    )


def _draw_broken_glyph(painter: QPainter, size: QSize, tokens: dict) -> None:
    """Flat muted background with a simple X, replacing v1's plain gray fill."""
    background = QColor(tokens.get("border_subtle", "#ECEEF2"))
    mark = QColor(tokens.get("text_muted", "#6B7280"))

    painter.setBrush(QBrush(background))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRect(0, 0, size.width(), size.height())

    pen = QPen(mark, 2)
    painter.setPen(pen)
    inset = size.width() * 0.32
    painter.drawLine(inset, inset, size.width() - inset, size.height() - inset)
    painter.drawLine(size.width() - inset, inset, inset, size.height() - inset)


def _draw_selection_badge(painter: QPainter, size: QSize, tokens: dict) -> None:
    """Filled accent-colored circle with a white checkmark, top-left corner."""
    accent = QColor(tokens.get("accent", "#4A56C6"))
    check_color = QColor(tokens.get("surface_white", "#FFFFFF"))

    cx = _BADGE_MARGIN + _BADGE_DIAMETER / 2
    cy = _BADGE_MARGIN + _BADGE_DIAMETER / 2

    painter.setBrush(QBrush(accent))
    painter.setPen(QPen(check_color, 2))
    painter.drawEllipse(QRectF(cx - _BADGE_DIAMETER / 2, cy - _BADGE_DIAMETER / 2, _BADGE_DIAMETER, _BADGE_DIAMETER))

    pen = QPen(check_color, 2)
    painter.setPen(pen)
    painter.drawLine(cx - 5, cy, cx - 1, cy + 4)
    painter.drawLine(cx - 1, cy + 4, cx + 6, cy - 5)
