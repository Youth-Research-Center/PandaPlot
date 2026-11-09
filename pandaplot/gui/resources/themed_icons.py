"""Theme-aware bundled icons for toolbars and buttons.

`themed_icon` renders a bundled icon in a design-token colour. Long-lived actions and buttons are bound to an `ActionIcons`
registry so their icons can be re-rendered when the theme changes (call `retint()` from the owner's `_apply_theme`).
Widgets that are rebuilt on demand can call `themed_icon` directly when they are built.
"""

import logging
from enum import Enum

import shiboken6
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QAbstractButton

from pandaplot.gui.resources.icon_library import build_icon
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager

DEFAULT_ICON_SIZE = 16


class IconRole(Enum):
    """Which design token tints an icon."""

    TEXT = "text_primary"
    MUTED = "text_muted"
    ACTIVE = "accent_icon_active"


def themed_icon(
    app_context: AppContext,
    name: str,
    *,
    role: IconRole = IconRole.TEXT,
    size: int = DEFAULT_ICON_SIZE,
) -> QIcon:
    """Render a bundled icon tinted for the current theme.

    Args:
        app_context: Provides the `ThemeManager` whose design tokens supply the colours.
        name: Icon name from `icon_manifest.toml`.
        role: Token that tints the icon in its normal state (the disabled state uses `text_disabled`).
        size: Logical pixel size of the square icon.

    Raises:
        KeyError: If the icon is not bundled.
    """
    tokens = app_context.get_manager(ThemeManager).get_design_tokens()
    return build_icon(name, tokens[role.value], size=size, disabled_color=tokens["text_disabled"])


class ActionIcons:
    """Registry of actions and buttons whose bundled icons follow the theme.

    Args:
        app_context: Provides the `ThemeManager` whose design tokens supply the colours.
        role: Token that tints the icons in their normal state.
        size: Logical pixel size of the square icons.
    """

    def __init__(
        self,
        app_context: AppContext,
        *,
        role: IconRole = IconRole.TEXT,
        size: int = DEFAULT_ICON_SIZE,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self._app_context = app_context
        self._role = role
        self._size = size
        self._bound: list[tuple[QAction | QAbstractButton, str]] = []

    def bind(self, target: QAction | QAbstractButton, name: str) -> None:
        """Set `target`'s icon now and re-render it on every `retint()`."""
        target.setIcon(themed_icon(self._app_context, name, role=self._role, size=self._size))
        self._bound.append((target, name))

    def retint(self) -> None:
        """Re-render every bound icon from the current theme tokens, dropping targets that no longer exist."""
        alive = [(target, name) for target, name in self._bound if shiboken6.isValid(target)]
        if len(alive) != len(self._bound):
            self.logger.debug("Dropped %d deleted icon targets", len(self._bound) - len(alive))
        self._bound = alive
        for target, name in alive:
            target.setIcon(themed_icon(self._app_context, name, role=self._role, size=self._size))
