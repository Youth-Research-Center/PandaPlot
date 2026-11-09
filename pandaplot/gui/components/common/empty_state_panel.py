"""EmptyStatePanel: a centered card explaining that a view has nothing to show yet, with up to two actions."""

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pandaplot.gui.components.common.card import Card
from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.components.common.p_button import ButtonRole, PButton
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager

CONTENT_MAX_WIDTH = 420
MAX_ACTIONS = 2
_ACTION_ROLES: tuple[ButtonRole, ...] = ("primary", "secondary")


class EmptyStatePanel(Card):
    """A centered heading, description and up to two action buttons for an empty view.

    The first action is styled as the primary button and the second as the secondary one. The panel's accessible
    name and description mirror the heading and description text. The owner forwards theme changes to `set_tokens`.

    Attributes:
        action_buttons: The action buttons in the order the actions were given.
    """

    def __init__(
        self,
        app_context: AppContext,
        *,
        heading: str,
        description: str,
        icon_name: str | None = None,
        actions: Sequence[tuple[str, Callable[[], None]]] = (),
        parent: QWidget | None = None,
    ) -> None:
        """Build the panel.

        Args:
            app_context: Application context, used for theme tokens and icons.
            heading: Short title of the empty state.
            description: Explanation of what the user can do next.
            icon_name: Bundled icon name shown above the heading, or None for no icon.
            actions: (label, callback) pairs, at most two.
            parent: Parent widget.

        Raises:
            ValueError: If more than two actions are given.
        """
        super().__init__(parent)
        if len(actions) > MAX_ACTIONS:
            raise ValueError(f"EmptyStatePanel supports at most {MAX_ACTIONS} actions, got {len(actions)}")
        self._app_context = app_context

        outer = QHBoxLayout(self)
        outer.addStretch(1)
        content = QWidget()
        content.setMaximumWidth(CONTENT_MAX_WIDTH)
        outer.addWidget(content, 100)
        outer.addStretch(1)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addStretch(1)

        self.icon_label: IconLabel | None = None
        if icon_name is not None:
            self.icon_label = IconLabel(app_context, icon_name, size=32)
            layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.heading_label = QLabel()
        self.heading_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.heading_label.setWordWrap(True)
        layout.addWidget(self.heading_label)

        self.description_label = QLabel()
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.action_buttons: list[PButton] = []
        if actions:
            buttons_row = QHBoxLayout()
            buttons_row.setSpacing(8)
            buttons_row.addStretch(1)
            for (label, callback), role in zip(actions, _ACTION_ROLES, strict=False):
                button = PButton(label, role=role, on_click=callback)
                self.action_buttons.append(button)
                buttons_row.addWidget(button)
            buttons_row.addStretch(1)
            layout.addSpacing(6)
            layout.addLayout(buttons_row)
        layout.addStretch(1)

        self.set_heading(heading)
        self.set_description(description)
        self.set_tokens(app_context.get_manager(ThemeManager).get_design_tokens())

    def set_heading(self, text: str) -> None:
        """Set the heading text and the panel's accessible name."""
        self.heading_label.setText(text)
        self.setAccessibleName(text)

    def set_description(self, text: str) -> None:
        """Set the description text and the panel's accessible description."""
        self.description_label.setText(text)
        self.setAccessibleDescription(text)

    def set_tokens(self, tokens: dict) -> None:
        """Apply theme tokens to the card, the texts and the icon."""
        super().set_tokens(tokens)
        text_primary = tokens.get("text_primary", "#1C1E26")
        text_muted = tokens.get("text_muted", "#6B7280")
        # Hosts may style every QFrame (QLabel is one) with a border and background;
        # reset both so the texts never render as boxed fields inside the card.
        plain = "border: none; background: transparent;"
        self.heading_label.setStyleSheet(f"{plain} font-size: 16px; font-weight: 600; color: {text_primary};")
        self.description_label.setStyleSheet(f"{plain} color: {text_muted};")
        if self.icon_label is not None:
            self.icon_label.setStyleSheet(plain)
            self.icon_label.retint()
