"""PButton: a QPushButton with a semantic role (color) and shape (icon vs
standard), both applied as Qt dynamic properties consumed by
ThemeManager's global QSS (see [secondary]/[destructive]/[primary]/[iconButton]
selectors in pandaplot/services/theme/theme_manager.py).

`on_click` and `enabled` let call sites fold their construction-time
`clicked.connect(...)`/`setEnabled(...)` calls directly into the constructor
call, instead of wiring them up afterward in a separate `_connect_signals()`
step; `on_click` accepts a plain callable, a bound Qt Signal, or a
`<signal>.emit` method.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from PySide6.QtCore import QEvent
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QWidget

ButtonRole = Literal["primary", "secondary", "destructive"]

_ROLES: tuple[ButtonRole, ...] = ("primary", "secondary", "destructive")


class PButton(QPushButton):
    def __init__(self, text: str = "", role: ButtonRole = "secondary", *,
                 icon: bool = False, on_click: Callable[..., object] | None = None,
                 enabled: bool = True, parent: QWidget | None = None):
        super().__init__(text, parent)
        self._normal_icon = QIcon()
        self._hover_icon: QIcon | None = None
        self._hovered = False
        self.setProperty("iconButton", icon)
        self.set_role(role)
        if on_click is not None:
            self.clicked.connect(on_click)
        if not enabled:
            self.setEnabled(False)

    def set_role(self, role: ButtonRole) -> None:
        for r in _ROLES:
            self.setProperty(r, r == role)
        self.style().unpolish(self)
        self.style().polish(self)

    def setIcon(self, icon: QIcon) -> None:
        """Set the icon shown when the button is not hovered (or has no hover icon)."""
        self._normal_icon = icon
        self._show_current_icon()

    def set_hover_icon(self, icon: QIcon | None) -> None:
        """Show `icon` instead of the normal icon while the mouse is over the enabled button.

        Qt does not switch a stylesheet-styled button to `QIcon.Mode.Active` on hover, so the swap is explicit. Pass `None`
        to go back to a single icon.
        """
        self._hover_icon = icon
        self._show_current_icon()

    def event(self, event: QEvent) -> bool:
        """Track the mouse entering and leaving to swap the hover icon, and the enabled state to drop it."""
        event_type = event.type()
        if event_type == QEvent.Type.Enter:
            self._hovered = True
            self._show_current_icon()
        elif event_type == QEvent.Type.Leave:
            self._hovered = False
            self._show_current_icon()
        elif event_type == QEvent.Type.EnabledChange:
            self._show_current_icon()
        return super().event(event)

    def _show_current_icon(self) -> None:
        use_hover = self._hover_icon is not None and self._hovered and self.isEnabled()
        super().setIcon(self._hover_icon if use_hover and self._hover_icon is not None else self._normal_icon)
