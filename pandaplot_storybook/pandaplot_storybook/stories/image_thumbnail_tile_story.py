from __future__ import annotations

from pandaplot.gui.components.common.image_thumbnail_tile import build_gallery_tile_icon
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from pandaplot_storybook.registry import BoolControl, ChoiceControl, StoryDef, story


def _sample_pixmap() -> QPixmap:
    """Synthetic gradient placeholder -- no real photo bytes needed for the
    story to stay self-contained."""
    size = QSize(120, 120)
    pixmap = QPixmap(size)
    gradient = QLinearGradient(0, 0, size.width(), size.height())
    gradient.setColorAt(0.0, QColor("#4A56C6"))
    gradient.setColorAt(1.0, QColor("#8A4BB8"))
    painter = QPainter(pixmap)
    painter.fillRect(pixmap.rect(), gradient)
    painter.end()
    return pixmap


class _GalleryTilePreview(QLabel):
    """Displays one tile built from the current control values."""

    def __init__(self):
        super().__init__()
        self._tile_type = "image"
        self._selected = False

    def set_type_and_selection(self, tile_type: str, *, selected: bool) -> None:
        self._tile_type = tile_type
        self._selected = selected

    def set_tokens(self, tokens: dict) -> None:
        pixmap = _sample_pixmap() if self._tile_type == "image" else None
        icon = build_gallery_tile_icon(
            pixmap, self._tile_type, selected=self._selected, tokens=tokens
        )
        self.setPixmap(icon.pixmap(QSize(120, 120)))


@story("ImageGalleryTile")
def _build() -> StoryDef:
    def make_widget(values: dict, tokens: dict) -> QWidget:
        preview = _GalleryTilePreview()
        preview.set_type_and_selection(values["tile_type"], selected=values["selected"])
        preview.set_tokens(tokens)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(preview)
        return container

    return StoryDef(
        controls=[
            ChoiceControl("tile_type", "image", ["image", "album", "broken"]),
            BoolControl("selected", default=False),
        ],
        make_widget=make_widget,
    )
