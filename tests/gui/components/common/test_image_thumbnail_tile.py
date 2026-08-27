import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.image_thumbnail_tile import build_gallery_tile_icon

_TOKENS = {
    "accent": "#4A56C6",
    "surface_white": "#FFFFFF",
    "text_muted": "#6B7280",
    "border_subtle": "#ECEEF2",
}


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _sample_pixmap() -> QPixmap:
    pixmap = QPixmap(QSize(40, 30))
    pixmap.fill(QColor("blue"))
    return pixmap


class TestBuildGalleryTileIcon:
    def test_image_type_returns_non_null_icon(self):
        icon = build_gallery_tile_icon(_sample_pixmap(), "image", selected=False, tokens=_TOKENS)

        assert not icon.isNull()

    def test_album_type_returns_non_null_icon_without_a_pixmap(self):
        icon = build_gallery_tile_icon(None, "album", selected=False, tokens=_TOKENS)

        assert not icon.isNull()

    def test_broken_type_returns_non_null_icon_without_a_pixmap(self):
        icon = build_gallery_tile_icon(None, "broken", selected=False, tokens=_TOKENS)

        assert not icon.isNull()

    def test_selected_and_unselected_icons_differ(self):
        unselected = build_gallery_tile_icon(_sample_pixmap(), "image", selected=False, tokens=_TOKENS)
        selected = build_gallery_tile_icon(_sample_pixmap(), "image", selected=True, tokens=_TOKENS)

        unselected_pixmap = unselected.pixmap(QSize(120, 120))
        selected_pixmap = selected.pixmap(QSize(120, 120))
        assert unselected_pixmap.toImage() != selected_pixmap.toImage()

    def test_respects_custom_size(self):
        icon = build_gallery_tile_icon(
            _sample_pixmap(), "image", selected=False, tokens=_TOKENS, size=QSize(64, 64)
        )

        pixmap = icon.pixmap(QSize(64, 64))
        assert pixmap.size() == QSize(64, 64)


class TestBuildGalleryTileIconCheckmarkPosition:
    def test_checkmark_badge_is_in_top_left_not_bottom_right(self):
        size = QSize(120, 120)
        unselected = build_gallery_tile_icon(
            _sample_pixmap(), "image", selected=False, tokens=_TOKENS, size=size
        )
        selected = build_gallery_tile_icon(
            _sample_pixmap(), "image", selected=True, tokens=_TOKENS, size=size
        )

        unselected_image = unselected.pixmap(size).toImage()
        selected_image = selected.pixmap(size).toImage()

        # Top-left corner should differ (badge is there when selected)
        top_left_differs = any(
            unselected_image.pixelColor(x, y) != selected_image.pixelColor(x, y)
            for x in range(0, 30) for y in range(0, 30)
        )
        assert top_left_differs, "expected the checkmark badge to appear in the top-left region"

        # Bottom-right corner should NOT differ (badge is no longer there)
        bottom_right_differs = any(
            unselected_image.pixelColor(x, y) != selected_image.pixelColor(x, y)
            for x in range(size.width() - 30, size.width()) for y in range(size.height() - 30, size.height())
        )
        assert not bottom_right_differs, "expected no badge remnant in the bottom-right region"
