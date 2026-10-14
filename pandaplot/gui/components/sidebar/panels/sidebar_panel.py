"""Shared base class for sidebar panels: a pinned title followed by a
content area that is either scrollable or added directly.

The panel look (background, group boxes, title, result text areas) is not set
per panel: ``SidebarPanel`` marks itself with the ``sidebarPanel`` property and
ThemeManager styles everything under it. A panel only styles what is specific
to it.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLabel, QScrollArea, QVBoxLayout, QWidget

from pandaplot.gui.components.sidebar.panels.panel_form_layout import compact_combo
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.state.app_context import AppContext

TITLE_OBJECT_NAME = "sidebarPanelTitle"
CONTENT_MARGIN = 4
SECTION_SPACING = 6


class SidebarPanel(PWidget):
    """Base class for sidebar panels.

    Subclasses call, in order, from their `_init_ui()`:
    1. `self._init_panel_layout()`
    2. `self._set_title("...")`
    3. build their content widget as today
    4. `self._set_content(content_widget, scrollable=...)`
    """

    def __init__(self, app_context: AppContext, parent: QWidget | None = None, **kwargs):
        super().__init__(app_context=app_context, parent=parent, **kwargs)
        self.main_layout: QVBoxLayout | None = None
        self.title_label: QLabel | None = None
        self.setProperty("sidebarPanel", True)  # noqa: FBT003 -- Qt dynamic-property API takes the value positionally
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # noqa: FBT003 -- Qt bound method, positional-only

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
        self.title_label.setObjectName(TITLE_OBJECT_NAME)
        self.main_layout.addWidget(self.title_label)
        return self.title_label

    def _new_content_layout(self, content: QWidget) -> QVBoxLayout:
        """Create the vertical layout of a panel's content widget.

        Every panel stacks its group boxes in one of these, with the same outer
        margin and the same gap between sections.

        Args:
            content: The widget handed to ``_set_content``.

        Returns:
            The layout, already installed on ``content``.
        """
        layout = QVBoxLayout(content)
        layout.setContentsMargins(CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN)
        layout.setSpacing(SECTION_SPACING)
        return layout

    def _set_content(self, widget: QWidget, *, scrollable: bool = True) -> None:
        """Add `widget` to `main_layout`, after the title.

        If `scrollable`, wrap `widget` in a frameless, resizable QScrollArea
        first, so only the content scrolls and the title stays pinned. Every
        combo box already in `widget` is made compact so a long item cannot
        widen the panel (see `compact_combo`).
        """
        assert self.main_layout is not None, "_init_panel_layout must run first"
        # Combos in rows that are not form fields (a combo beside a button, in a
        # grid) are made compact here; form rows do it in PanelFormLayout.addRow.
        for combo in widget.findChildren(QComboBox):
            compact_combo(combo)
        if scrollable:
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_area.setWidget(widget)
            self.main_layout.addWidget(scroll_area)
        else:
            self.main_layout.addWidget(widget)
