"""Shared base class for sidebar panels: a pinned title followed by a
content area that is either scrollable or added directly.
"""

from typing import override

import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QToolButton, QVBoxLayout, QWidget

from pandaplot.gui.components.common.help_button import build_help_button, help_button_stylesheet
from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events.event_types import UIEvents
from pandaplot.models.state.app_context import AppContext


class SidebarPanel(PWidget):
    """Base class for sidebar panels.

    Subclasses call, in order, from their `_init_ui()`:
    1. `self._init_panel_layout()`
    2. `self._set_title("...")`
    3. build their content widget as today
    4. `self._set_content(content_widget, scrollable=...)`
    """

    ICON_NAME: str | None = None  # bundled icon shown before the title

    def __init__(self, app_context: AppContext, parent: QWidget | None = None, **kwargs):
        super().__init__(app_context=app_context, parent=parent, **kwargs)
        self.main_layout: QVBoxLayout | None = None
        self.title_label: QLabel | None = None
        self.title_icon: IconLabel | None = None
        self.help_button: QToolButton | None = None
        self.help_topic: str | None = None
        self._title_row: QWidget | None = None

    def _init_panel_layout(self) -> QVBoxLayout:
        """Create `self.main_layout` with the shared panel margins/spacing."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(8)
        return self.main_layout

    def _set_title(self, text: str, *, help_topic: str | None = None) -> QLabel:
        """Create the title row and pin it at the top of `main_layout`.

        The row holds the `ICON_NAME` icon (when set), `title_label` and, when a help topic is given, a help button.

        Args:
            text: Title text, without an icon: the icon comes from `ICON_NAME`.
            help_topic: Help topic id. When given, a "?" button that opens that
                topic in the Help window is placed beside the title.

        Returns:
            The title label.
        """
        assert self.main_layout is not None, "_init_panel_layout must run first"
        self.title_label = QLabel(text)
        self.help_topic = help_topic

        self._title_row = QWidget()
        self._title_row.setObjectName("panelTitleRow")
        row_layout = QHBoxLayout(self._title_row)
        row_layout.setContentsMargins(6 if self.ICON_NAME is not None else 0, 0, 4, 0)
        row_layout.setSpacing(4)
        if self.ICON_NAME is not None:
            self.title_icon = IconLabel(self.app_context, self.ICON_NAME)
            row_layout.addWidget(self.title_icon)
        row_layout.addWidget(self.title_label, 1)

        if help_topic is not None:
            self.help_button = build_help_button(
                accessible_name=f"Help: {text}",
                accessible_description=f"Opens the Help window on the {text} topic",
                tooltip="Open help for this panel",
            )
            self.help_button.clicked.connect(self._on_help_clicked)
            row_layout.addWidget(self.help_button)

        self.main_layout.addWidget(self._title_row)
        return self.title_label

    @override
    def _on_theme_changed(self, event_data: dict) -> None:
        """Re-tint the title icon after the normal theme handling."""
        super()._on_theme_changed(event_data)
        if self.title_icon is not None and shiboken6.isValid(self.title_icon):
            self.title_icon.retint()

    def _on_help_clicked(self, _checked: bool = False) -> None:  # noqa: FBT001, FBT002 -- Qt clicked(bool) slot signature
        """Ask the Help window to open this panel's topic."""
        if self.help_topic is not None:
            self.publish_event(UIEvents.HELP_REQUESTED, {"topic_id": self.help_topic})

    def _set_content(self, widget: QWidget, *, scrollable: bool = True) -> None:
        """Add `widget` to `main_layout`, after the title.

        If `scrollable`, wrap `widget` in a frameless, resizable QScrollArea
        first, so only the content scrolls and the title stays pinned.
        """
        assert self.main_layout is not None, "_init_panel_layout must run first"
        if scrollable:
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_area.setWidget(widget)
            self.main_layout.addWidget(scroll_area)
        else:
            self.main_layout.addWidget(widget)

    @staticmethod
    def _follow_column_rename(names: list, event_data: dict) -> list[str]:
        """Map selected column names through a column event payload, as text.

        Pickers show ``str(label)`` while payloads carry the raw label (an Excel
        header can be an int), so names are compared and returned as text.

        Args:
            names: Column names selected before the event.
            event_data: A ``DATASET_COLUMN_*`` payload. Only a rename carries ``old_name``/``new_name``.

        Returns:
            ``names`` as text, with the renamed column replaced by its new name.
        """
        texts = [str(name) for name in names]
        if "old_name" not in event_data:
            return texts
        old_name, new_name = str(event_data["old_name"]), str(event_data.get("new_name"))
        return [new_name if text == old_name else text for text in texts]

    @staticmethod
    def _column_selection_changed(kept: list, current: list) -> bool:
        """Whether rebuilding a column picker changed which columns are selected.

        The analysis panels share this rule: when it returns True, the shown
        result no longer describes the selection and must be cleared. Names are
        compared as text and in any order; pickers restore the kept order.

        Args:
            kept: Columns the picker was asked to keep (see `_follow_column_rename`).
            current: Columns selected after the rebuild.

        Returns:
            True if a kept column is no longer selected or another column became selected.
        """
        return {str(name) for name in kept} != {str(name) for name in current}

    @staticmethod
    def title_stylesheet(base_fg: str, card_border: str) -> str:
        """Shared title-label stylesheet, parameterized by theme colors."""
        return (
            f"font-size: 14px; font-weight: bold; color: {base_fg}; "
            f"padding: 5px; background-color: {card_border}; border-radius: 3px;"
        )

    def _apply_title_theme(self, base_fg: str, card_border: str) -> None:
        """Apply the shared title styling, for subclasses' `_apply_theme()` to
        call instead of each repeating the same setStyleSheet line.

        Without an icon or help button the band is `title_stylesheet` on
        `title_label`. With either, the band moves to the row container so
        they sit inside it, and the label and button are drawn on top of it.

        Guarded since `title_label` is only set once `_set_title()` runs, and
        `_apply_theme()` can in principle be invoked before that (e.g. via the
        base ThemeEvents.THEME_CHANGED subscription) depending on subclass
        init order."""
        title_label = getattr(self, "title_label", None)
        if title_label is None:
            return
        title_row = getattr(self, "_title_row", None)
        help_button = getattr(self, "help_button", None)
        if title_row is None or (help_button is None and getattr(self, "title_icon", None) is None):
            title_label.setStyleSheet(self.title_stylesheet(base_fg, card_border))
            return
        title_row.setStyleSheet(f"QWidget#panelTitleRow {{ background-color: {card_border}; border-radius: 3px; }}")
        title_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {base_fg}; padding: 5px; background-color: transparent;")
        if help_button is not None:
            help_button.setStyleSheet(help_button_stylesheet(base_fg))
