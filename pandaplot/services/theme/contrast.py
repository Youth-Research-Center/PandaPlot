"""WCAG 2.x contrast helpers for the design tokens and the theme manager."""

from PySide6.QtGui import QColor

_STEP_FACTORS = range(100, 405, 5)


def relative_luminance(color: QColor) -> float:
    """Return the WCAG 2.x relative luminance of `color` (0 for black, 1 for white)."""

    def channel(value: int) -> float:
        c = value / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(color.red()) + 0.7152 * channel(color.green()) + 0.0722 * channel(color.blue())


def contrast_ratio(first: QColor, second: QColor) -> float:
    """Return the WCAG 2.x contrast ratio between two colours, from 1 to 21."""
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def contrasting_text_color(background: QColor) -> QColor:
    """Return black or white, whichever has the higher contrast against `background`."""
    luminance = relative_luminance(background)
    white = 1.05 / (luminance + 0.05)
    black = (luminance + 0.05) / 0.05
    return QColor(255, 255, 255) if white >= black else QColor(0, 0, 0)


def adjust_until_contrast(start: QColor, background: QColor, *, min_ratio: float, lighten: bool) -> QColor:
    """Lighten or darken `start` in 5 % steps until it reaches `min_ratio` against `background`.

    Args:
        start: The colour to begin from; returned unchanged when it already passes.
        background: The colour it must stand out against.
        min_ratio: Required WCAG contrast ratio (4.5 for text, 3 for graphics).
        lighten: Step lighter (dark backgrounds) instead of darker (light backgrounds).

    Returns:
        The first passing step, or black/white (whichever contrasts more) when no step passes.
    """
    for factor in _STEP_FACTORS:
        candidate = start.lighter(factor) if lighten else start.darker(factor)
        if contrast_ratio(candidate, background) >= min_ratio:
            return candidate
    return contrasting_text_color(background)


def mix(first: str, second: str, amount: float) -> str:
    """Mix two `#RRGGBB` colours channel by channel; `amount` 0 gives `first`, 1 gives `second`.

    Returns:
        The mixed colour as upper-case `#RRGGBB`.
    """
    a, b = QColor(first), QColor(second)
    channels = (
        round(x + (y - x) * amount) for x, y in ((a.red(), b.red()), (a.green(), b.green()), (a.blue(), b.blue()))
    )
    return "#" + "".join(f"{value:02X}" for value in channels)
