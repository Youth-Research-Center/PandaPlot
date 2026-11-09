"""Shared helpers for tests that check bundled, theme-tinted icons."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap

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
)


def _light_theme_tokens() -> dict[str, str]:
    manager = ThemeManager.__new__(ThemeManager)
    manager._current = ThemeContext(theme=Theme.LIGHT, accent="#4A56C6", interface_font_size=10)
    tokens = manager.get_design_tokens()
    return {key: tokens[key] for key in _TOKEN_KEYS}


ICON_TOKENS: dict[str, str] = _light_theme_tokens()
"""Light-theme design tokens that icons and status roles read, taken from the real `ThemeManager`."""


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
