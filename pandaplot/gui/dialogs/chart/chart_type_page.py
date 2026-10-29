"""Step 1 of the chart creation wizard: pick a chart type, see a live preview.

`ChartCanvas` (and the matplotlib it pulls in) is imported lazily inside
`_render_preview`, not at module scope, so this page stays safe to import
from anywhere in the app's menu/command wiring without eagerly loading
matplotlib (see tests/gui/test_main_menu_lazy_imports.py).
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.card import Card
from pandaplot.gui.components.common.grouped_list import GroupedListWidget, configure_group_header
from pandaplot.gui.components.common.section_header import SectionHeader
from pandaplot.gui.core.widget_extension import PWizardPage
from pandaplot.gui.dialogs.chart.chart_type_icons import chart_type_icon
from pandaplot.gui.dialogs.chart.wizard_footer import WizardFooter
from pandaplot.gui.dialogs.chart.wizard_step_rail import WizardStepRail
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_CATEGORIES, CHART_TYPE_SPECS
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class ChartTypePage(PWizardPage):
    emptyRequested = Signal()

    def __init__(self, app_context: AppContext, parent: QWidget | None = None):
        super().__init__(app_context=app_context, parent=parent)
        self._preview_canvas = None
        self._tokens: dict = {}
        self._initialize()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.step_rail = WizardStepRail(["Type", "Data", "Labels"])
        rail_row = QHBoxLayout()
        rail_row.setContentsMargins(14, 10, 14, 10)
        rail_row.addWidget(self.step_rail)
        outer.addLayout(rail_row)

        content = QHBoxLayout()
        content.setContentsMargins(14, 14, 14, 14)
        outer.addLayout(content, 1)

        type_column = QVBoxLayout()
        type_card = Card()
        type_layout = QVBoxLayout(type_card)
        type_layout.addWidget(SectionHeader("Chart type"))

        self.type_list = GroupedListWidget()
        self.type_list.setAccessibleName("Chart type")
        for category, chart_types in CHART_TYPE_CATEGORIES.items():
            # Same rule as GroupedValueComboBox: no header for an empty group.
            if not chart_types:
                continue
            # A header can't be selected and keyboard navigation skips it
            # (see grouped_list.py). It carries no UserRole data, which is
            # how the rest of this page tells it apart from a chart type row.
            header = QListWidgetItem(category.value)
            configure_group_header(header, category.value)
            self.type_list.addItem(header)
            for chart_type in chart_types:
                item = QListWidgetItem(CHART_TYPE_SPECS[chart_type].display_name)
                item.setData(Qt.ItemDataRole.UserRole, chart_type)
                self.type_list.addItem(item)
        self.type_list.currentItemChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_list, 1)
        type_column.addWidget(type_card, 1)
        content.addLayout(type_column, 0)

        preview_column = QVBoxLayout()
        preview_card = Card()
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.addWidget(SectionHeader("Preview"))
        self.preview_container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_container.setLayout(container_layout)
        preview_layout.addWidget(self.preview_container, 1)
        preview_column.addWidget(preview_card, 1)
        content.addLayout(preview_column, 1)

        self.footer = WizardFooter(step_number=1, total_steps=3, show_empty_link=True)
        self.footer.nextClicked.connect(lambda: self.wizard().next())
        self.footer.cancelClicked.connect(lambda: self.wizard().reject())
        self.footer.emptyRequested.connect(self.emptyRequested.emit)
        self.empty_button = self.footer.empty_link
        outer.addWidget(self.footer)

        self.completeChanged.connect(lambda: self.footer.set_next_enabled(enabled=self.isComplete()))
        self.footer.set_next_enabled(enabled=self.isComplete())

        # Row 0 is a category header; making it current would leave the
        # page with no chart type selected.
        first_type_row = self._first_type_row()
        if first_type_row is not None:
            self.type_list.setCurrentRow(first_type_row)

    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        self._apply_tokens(theme_manager.get_design_tokens())

    def _apply_tokens(self, tokens: dict):
        self._tokens = tokens
        self.step_rail.set_tokens(tokens)
        self.footer.set_tokens(tokens)
        accent = tokens.get("accent", "#4A56C6")
        text_secondary = tokens.get("text_secondary", "#3F4350")
        text_muted = tokens.get("text_muted", "#6B7280")
        border = tokens.get("border_control", "#DCDEE4")
        selected_bg = tokens.get("accent_selected_bg", "#EEF0FB")
        self.type_list.setStyleSheet(f"""
            QListWidget {{ border: none; outline: none; }}
            QListWidget::item {{
                border: 1px solid {border}; border-radius: 5px;
                padding: 7px 9px; margin-bottom: 4px; color: {text_secondary};
            }}
            QListWidget::item:selected {{
                border: 1px solid {accent}; background: {selected_bg}; color: {accent};
            }}
            QListWidget::item:disabled {{
                border: none; background: transparent; color: {text_muted};
                padding: 8px 2px 2px 2px; margin-bottom: 0px;
            }}
        """)
        for row in range(self.type_list.count()):
            item = self.type_list.item(row)
            chart_type = item.data(Qt.ItemDataRole.UserRole)
            if chart_type is None:
                continue
            icon_color = accent if row == self.type_list.currentRow() else text_secondary
            item.setIcon(chart_type_icon(chart_type, icon_color))

    def _on_type_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None):
        if current is None:
            return
        chart_type = current.data(Qt.ItemDataRole.UserRole)
        if chart_type is None:
            # A category header was made current (only possible from code:
            # keyboard and mouse never land on one). Keep the previous chart
            # type rather than preview nothing and disable Next; its preview
            # is still showing, so signals are blocked to skip a redraw.
            if previous is not None and previous.data(Qt.ItemDataRole.UserRole) is not None:
                self.type_list.blockSignals(True)  # noqa: FBT003 -- Qt bound method, positional-only
                self.type_list.setCurrentItem(previous)
                self.type_list.blockSignals(False)  # noqa: FBT003 -- Qt bound method, positional-only
            return
        self._render_preview(chart_type)
        self.completeChanged.emit()
        self._apply_tokens(self._tokens)

    def _render_preview(self, chart_type: str):
        # Imported here, not at module scope, for the same reason ChartCanvas
        # is: wizard_preview pulls in matplotlib (see this module's
        # docstring and tests/gui/test_main_menu_lazy_imports.py).
        from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas
        from pandaplot.gui.dialogs.chart.wizard_preview import draw_chart_type_sample

        if self._preview_canvas is not None:
            self.preview_container.layout().removeWidget(self._preview_canvas)
            self._preview_canvas.setParent(None)
            self._preview_canvas.deleteLater()

        canvas = ChartCanvas(width=4, height=3, dpi=80)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Shared with the Labels step's own sample fallback, so a chart type
        # can't preview differently in the two steps of one wizard.
        draw_chart_type_sample(canvas, chart_type)
        canvas.draw()

        self.preview_container.layout().addWidget(canvas)
        self._preview_canvas = canvas

    def _first_type_row(self) -> int | None:
        return next(
            (row for row in range(self.type_list.count()) if self.type_list.item(row).data(Qt.ItemDataRole.UserRole) is not None),
            None,
        )

    def selected_chart_type(self) -> str | None:
        item = self.type_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def isComplete(self) -> bool:
        return self.selected_chart_type() is not None

    def nextId(self) -> int:
        wizard = self.wizard()
        no_dataset_page_id = getattr(wizard, "_no_dataset_page_id", None)
        if no_dataset_page_id is not None and getattr(wizard, "_no_dataset_mode", False):
            return no_dataset_page_id
        return super().nextId()
