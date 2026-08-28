"""Shared base class for sidebar panels: a pinned title followed by a
content area that is either scrollable or added directly.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.state.app_context import AppContext


class SidebarPanel(PWidget):
    """Base class for sidebar panels.

    Subclasses call, in order, from their `_init_ui()`:
    1. `self._init_panel_layout()`
    2. `self._set_title("...")`
    3. build their content widget as today
    4. `self._set_content(content_widget, scrollable=...)`
    """

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None, **kwargs):
        super().__init__(app_context=app_context, parent=parent, **kwargs)
        self.main_layout: Optional[QVBoxLayout] = None
        self.title_label: Optional[QLabel] = None

    def _init_panel_layout(self) -> QVBoxLayout:
        """Create `self.main_layout` with the shared panel margins/spacing."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(8)
        return self.main_layout

    def _set_title(self, text: str) -> QLabel:
        """Create `self.title_label` and pin it at the top of `main_layout`."""
        assert self.main_layout is not None, "_init_panel_layout must run first"
        self.title_label = QLabel(text)
        self.main_layout.addWidget(self.title_label)
        return self.title_label

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
    def title_stylesheet(base_fg: str, card_border: str) -> str:
        """Shared title-label stylesheet, parameterized by theme colors."""
        return (
            f"font-size: 14px; font-weight: bold; color: {base_fg}; "
            f"padding: 5px; background-color: {card_border}; border-radius: 3px;"
        )

    def _apply_title_theme(self, base_fg: str, card_border: str) -> None:
        """Apply `title_stylesheet` to `title_label`, for subclasses'
        `_apply_theme()` to call instead of each repeating the same
        setStyleSheet line. Guarded since `title_label` is only set once
        `_set_title()` runs, and `_apply_theme()` can in principle be
        invoked before that (e.g. via the base ThemeEvents.THEME_CHANGED
        subscription) depending on subclass init order."""
        if self.title_label is not None:
            self.title_label.setStyleSheet(self.title_stylesheet(base_fg, card_border))
