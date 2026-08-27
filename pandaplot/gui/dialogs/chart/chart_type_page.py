"""Step 1 of the chart creation wizard: pick a chart type, see a live preview.

`ChartCanvas` (and the matplotlib it pulls in) is imported lazily inside
`_render_preview`, not at module scope, so this page stays safe to import
from anywhere in the app's menu/command wiring without eagerly loading
matplotlib (see tests/gui/test_main_menu_lazy_imports.py).
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.card import Card
from pandaplot.gui.components.common.section_header import SectionHeader
from pandaplot.gui.core.widget_extension import PWizardPage
from pandaplot.gui.dialogs.chart.chart_type_icons import chart_type_icon
from pandaplot.gui.dialogs.chart.wizard_footer import WizardFooter
from pandaplot.gui.dialogs.chart.wizard_step_rail import WizardStepRail
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager

_SAMPLE_X = [1, 2, 3, 4, 5]
_SAMPLE_Y = [2, 3, 1, 4, 3]
_SAMPLE_U = [1.0, 0.5, -1.0, 0.5, -0.5]
_SAMPLE_V = [0.5, -1.0, 0.5, 1.0, -0.5]


class ChartTypePage(PWizardPage):
    emptyRequested = Signal()

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
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

        self.type_list = QListWidget()
        for chart_type, spec in CHART_TYPE_SPECS.items():
            item = QListWidgetItem(spec.display_name)
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

        self.type_list.setCurrentRow(0)

    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        self._apply_tokens(theme_manager.get_design_tokens())

    def _apply_tokens(self, tokens: dict):
        self._tokens = tokens
        self.step_rail.set_tokens(tokens)
        self.footer.set_tokens(tokens)
        accent = tokens.get("accent", "#4A56C6")
        text_secondary = tokens.get("text_secondary", "#3F4350")
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
        """)
        for row in range(self.type_list.count()):
            item = self.type_list.item(row)
            chart_type = item.data(Qt.ItemDataRole.UserRole)
            icon_color = accent if row == self.type_list.currentRow() else text_secondary
            item.setIcon(chart_type_icon(chart_type, icon_color))

    def _on_type_changed(self, current: Optional[QListWidgetItem], _previous):
        if current is None:
            return
        self._render_preview(current.data(Qt.ItemDataRole.UserRole))
        self.completeChanged.emit()
        self._apply_tokens(self._tokens)

    def _render_preview(self, chart_type: str):
        from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas

        if self._preview_canvas is not None:
            self.preview_container.layout().removeWidget(self._preview_canvas)
            self._preview_canvas.setParent(None)
            self._preview_canvas.deleteLater()

        canvas = ChartCanvas(width=4, height=3, dpi=80)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        axes = canvas.axes
        if chart_type == "line":
            axes.plot(_SAMPLE_X, _SAMPLE_Y)
        elif chart_type == "scatter":
            axes.scatter(_SAMPLE_X, _SAMPLE_Y)
        elif chart_type == "bar":
            axes.bar(_SAMPLE_X, _SAMPLE_Y)
        elif chart_type == "hist":
            axes.hist(_SAMPLE_Y, bins=5)
        elif chart_type == "vector":
            axes.quiver(_SAMPLE_X, _SAMPLE_Y, _SAMPLE_U, _SAMPLE_V)
        elif chart_type == "colormap":
            axes.scatter(_SAMPLE_X, _SAMPLE_Y, c=_SAMPLE_Y, cmap="viridis")
        elif chart_type == "heatmap":
            import numpy as np
            grid = np.arange(16).reshape(4, 4)
            axes.pcolormesh(grid, cmap="viridis")
        canvas.draw()

        self.preview_container.layout().addWidget(canvas)
        self._preview_canvas = canvas

    def selected_chart_type(self) -> Optional[str]:
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
