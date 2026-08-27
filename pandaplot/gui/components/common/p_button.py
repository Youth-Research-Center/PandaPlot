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

from typing import Callable, Literal, Optional

from PySide6.QtWidgets import QPushButton, QWidget

ButtonRole = Literal["primary", "secondary", "destructive"]

_ROLES: tuple[ButtonRole, ...] = ("primary", "secondary", "destructive")


class PButton(QPushButton):
    def __init__(self, text: str = "", role: ButtonRole = "secondary", *,
                 icon: bool = False, on_click: Optional[Callable[..., object]] = None,
                 enabled: bool = True, parent: Optional[QWidget] = None):
        super().__init__(text, parent)
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
