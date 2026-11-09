"""Shared "?" help button, used by the sidebar panel titles and the chart wizard footer."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton, QWidget


def build_help_button(
    *, accessible_name: str, accessible_description: str, tooltip: str, parent: QWidget | None = None
) -> QToolButton:
    """Build a "?" tool button that is keyboard-focusable and screen-reader friendly.

    Args:
        accessible_name: Accessible name announced by screen readers.
        accessible_description: Accessible description announced by screen readers.
        tooltip: Tooltip text.
        parent: Optional parent widget.

    Returns:
        The configured button. The caller connects `clicked` and applies a stylesheet.
    """
    button = QToolButton(parent)
    button.setText("?")
    button.setToolTip(tooltip)
    button.setAccessibleName(accessible_name)
    button.setAccessibleDescription(accessible_description)
    button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def help_button_stylesheet(fg: str) -> str:
    """Stylesheet for a help button drawn on a coloured band, using only the foreground colour.

    Args:
        fg: Foreground colour (also the hover and focus border colour).

    Returns:
        The stylesheet text.
    """
    return (
        f"QToolButton {{ background-color: transparent; color: {fg}; font-weight: bold; "
        f"border: 1px solid transparent; border-radius: 3px; padding: 2px 6px; }}"
        f"QToolButton:hover {{ border: 1px solid {fg}; }}"
        f"QToolButton:focus {{ border: 2px solid {fg}; }}"
    )
