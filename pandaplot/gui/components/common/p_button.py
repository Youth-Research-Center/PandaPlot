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
from typing import Literal, override

from PySide6.QtCore import QEvent
from PySide6.QtGui import QEnterEvent, QIcon, QPixmap
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
        self._showing_hover = False
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

    @override
    def setIcon(self, icon: QIcon | QPixmap, /) -> None:
        """Set the icon shown when the button is not hovered (or has no hover icon)."""
        self._normal_icon = icon if isinstance(icon, QIcon) else QIcon(icon)
        if not self._showing_hover:
            super().setIcon(self._normal_icon)

    def set_hover_icon(self, icon: QIcon | None) -> None:
        """Show `icon` instead of the normal icon while the mouse is over the enabled button.

        Qt does not switch a stylesheet-styled button to `QIcon.Mode.Active` on hover, so the swap is explicit. Pass `None`
        to go back to a single icon.
        """
        self._hover_icon = icon
        self._sync_icon(refresh=True)

    @override
    def enterEvent(self, event: QEnterEvent) -> None:
        """Swap in the hover icon when the mouse enters the button."""
        self._hovered = True
        self._sync_icon()
        super().enterEvent(event)

    @override
    def leaveEvent(self, event: QEvent) -> None:
        """Restore the normal icon when the mouse leaves the button."""
        self._hovered = False
        self._sync_icon()
        super().leaveEvent(event)

    @override
    def changeEvent(self, event: QEvent) -> None:
        """Drop the hover icon when the button becomes disabled."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange:
            self._sync_icon()

    def _sync_icon(self, *, refresh: bool = False) -> None:
        """Show the hover or the normal icon, calling `QAbstractButton.setIcon` only when the shown icon changes.

        `QAbstractButton.setIcon` requests a layout, so a button without a hover icon must never reach it from hover or
        enabled-state changes.

        Args:
            refresh: Re-apply the hover icon even if it is already shown (the hover icon itself was replaced).
        """
        want_hover = self._hover_icon is not None and self._hovered and self.isEnabled()
        if want_hover == self._showing_hover and not (refresh and want_hover):
            return
        self._showing_hover = want_hover
        super().setIcon(self._hover_icon if want_hover and self._hover_icon is not None else self._normal_icon)
