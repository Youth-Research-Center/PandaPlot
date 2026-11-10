"""Theme-aware bundled icons for toolbars and buttons.

`themed_icon` renders a bundled icon in a design-token colour. Long-lived actions and buttons are bound to an `ActionIcons`
registry so their icons can be re-rendered when the theme changes (call `retint()` from the owner's `_apply_theme`).
Widgets that are rebuilt on demand can call `themed_icon` directly when they are built.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

import shiboken6
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QAbstractButton

from pandaplot.gui.resources.icon_library import build_icon
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager

DEFAULT_ICON_SIZE = 16


@runtime_checkable
class SupportsHoverIcon(Protocol):
    """A button that can show a different icon while the mouse is over it (`PButton`)."""

    def set_hover_icon(self, icon: QIcon | None) -> None:
        """Show `icon` instead of the normal icon while hovered; `None` goes back to a single icon."""


class IconRole(Enum):
    """Which design token tints an icon."""

    TEXT = "text_primary"
    MUTED = "text_muted"
    ACTIVE = "accent_icon_active"
    SUCCESS = "status_success"
    ERROR = "status_danger"
    WARNING = "status_modified_text"
    INFO = "accent"
    ON_ACCENT = "text_on_accent"
    ON_DANGER = "text_on_danger"


def themed_icon(
    app_context: AppContext,
    name: str,
    *,
    role: IconRole = IconRole.TEXT,
    size: int = DEFAULT_ICON_SIZE,
    selected_color: str | None = None,
) -> QIcon:
    """Render a bundled icon tinted for the current theme.

    Args:
        app_context: Provides the `ThemeManager` whose design tokens supply the colours.
        name: Icon name from `icon_manifest.toml`.
        role: Token that tints the icon in its normal state (the disabled state uses `text_disabled`).
        size: Logical pixel size of the square icon.
        selected_color: Colour of the icon on a selected row; Qt derives it from the normal state when omitted.

    Raises:
        KeyError: If the icon is not bundled.
    """
    tokens = app_context.get_manager(ThemeManager).get_design_tokens()
    return build_icon(name, tokens[role.value], size=size, disabled_color=tokens["text_disabled"], selected_color=selected_color)


@dataclass(frozen=True)
class _Binding:
    """An action or button bound to a bundled icon, with optional per-binding roles."""

    target: QAction | QAbstractButton
    name: str
    role: IconRole | None
    hover_role: IconRole | None


class ActionIcons:
    """Registry of actions and buttons whose bundled icons follow the theme.

    Args:
        app_context: Provides the `ThemeManager` whose design tokens supply the colours.
        role: Default token that tints the icons in their normal state; `bind(role=...)` overrides it per icon.
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
        self._bound: list[_Binding] = []

    def bind(
        self,
        target: QAction | QAbstractButton,
        name: str,
        *,
        role: IconRole | None = None,
        hover_role: IconRole | None = None,
    ) -> None:
        """Set `target`'s icon now and re-render it on every `retint()`.

        Args:
            target: The action or button to give the icon.
            name: Icon name from `icon_manifest.toml`.
            role: Token that tints this icon; the registry's role when omitted.
            hover_role: Token that tints the icon shown while a `PButton` is hovered; ignored for other targets.
        """
        binding = _Binding(target, name, role, hover_role)
        self._apply(binding)
        self._bound.append(binding)

    def retint(self) -> None:
        """Re-render every bound icon from the current theme tokens, dropping targets that no longer exist."""
        alive = [binding for binding in self._bound if shiboken6.isValid(binding.target)]
        if len(alive) != len(self._bound):
            self.logger.debug("Dropped %d deleted icon targets", len(self._bound) - len(alive))
        self._bound = alive
        for binding in alive:
            self._apply(binding)

    def _apply(self, binding: "_Binding") -> None:
        binding.target.setIcon(themed_icon(self._app_context, binding.name, role=binding.role or self._role, size=self._size))
        if binding.hover_role is None:
            return
        if isinstance(binding.target, SupportsHoverIcon):
            binding.target.set_hover_icon(themed_icon(self._app_context, binding.name, role=binding.hover_role, size=self._size))
        else:
            self.logger.debug("hover_role ignored for %s: it does not support hover icons", type(binding.target).__name__)
