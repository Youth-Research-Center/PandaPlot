"""Shared helpers for tests that check bundled, theme-tinted icons."""

from collections.abc import Mapping
from types import MappingProxyType

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem, QTreeWidget, QTreeWidgetItem

from pandaplot.models.state.config import Theme
from pandaplot.services.theme.theme_manager import ThemeContext, ThemeManager

_TOKEN_KEYS = (
    "text_primary",
    "text_muted",
    "accent_icon_active",
    "text_disabled",
    "status_success",
    "status_danger",
    "status_modified_text",
    "accent",
    "text_on_accent",
    "text_on_danger",
)


def _light_theme_tokens() -> dict[str, str]:
    manager = ThemeManager.__new__(ThemeManager)
    manager._current = ThemeContext(theme=Theme.LIGHT, accent="#4A56C6", interface_font_size=10)
    tokens = manager.get_design_tokens()
    return {key: tokens[key] for key in _TOKEN_KEYS}


ICON_TOKENS: Mapping[str, str] = MappingProxyType(_light_theme_tokens())
"""Read-only light-theme design tokens that icons and status roles read, taken from the real `ThemeManager`.

Hand a mock a `fresh_icon_tokens()` copy instead of this mapping, so a test that edits its tokens cannot change the shared ones.
"""


def fresh_icon_tokens() -> dict[str, str]:
    """Return a new, mutable copy of `ICON_TOKENS`."""
    return dict(ICON_TOKENS)


def strongest_pixel(source: QImage | QPixmap | QIcon, size: int = 32) -> QColor:
    """Return the most opaque pixel of an image, pixmap or icon (rendered at `size`), i.e. the icon's tint."""
    if isinstance(source, QIcon):
        source = source.pixmap(QSize(size, size))
    image = source.toImage() if isinstance(source, QPixmap) else source
    pixels = (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()))
    return max(pixels, key=lambda pixel: pixel.alpha())


def assert_tinted(actual: QColor, expected_hex: str, *, tolerance: int = 12) -> None:
    """Assert that `actual` is within `tolerance` of `expected_hex` on every colour channel."""
    wanted = QColor(expected_hex)
    assert abs(actual.red() - wanted.red()) < tolerance, f"{actual.name()} is not {wanted.name()}"
    assert abs(actual.green() - wanted.green()) < tolerance, f"{actual.name()} is not {wanted.name()}"
    assert abs(actual.blue() - wanted.blue()) < tolerance, f"{actual.name()} is not {wanted.name()}"


def hovered_selected_row_background(tree: QTreeWidget, row: QTreeWidgetItem) -> QColor:
    """Paint `row` as a selected row under the mouse and return the background colour at its right-hand side.

    The option is forged rather than driven by a real mouse because hover state is process-wide (`QCursor::pos()`, popups left
    open by earlier tests), which makes synthetic mouse moves unreliable in loaded parallel runs. The tree's own stylesheet and
    delegate paint the row, so a missing `QTreeWidget::item:selected:hover` rule shows up as the plain hover colour.
    """
    index = tree.indexFromItem(row)
    rect = tree.visualRect(index)
    option = QStyleOptionViewItem()
    option.initFrom(tree.viewport())
    option.rect = QRect(0, 0, 200, max(rect.height(), 20))
    option.widget = tree
    tree.itemDelegate().initStyleOption(option, index)
    option.state |= QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver | QStyle.StateFlag.State_Enabled
    image = QImage(option.rect.size(), QImage.Format.Format_ARGB32)
    image.fill(QColor("#000000"))
    painter = QPainter(image)
    try:
        tree.itemDelegate().paint(painter, option, index)
    finally:
        painter.end()
    return image.pixelColor(option.rect.width() - 4, option.rect.height() // 2)
