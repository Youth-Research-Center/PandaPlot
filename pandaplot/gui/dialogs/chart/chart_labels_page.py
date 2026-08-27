"""Step 3 of the chart creation wizard: title/subtitle, X/Y axis labels,
legend/grid toggles."""
from typing import Optional

from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.card import Card
from pandaplot.gui.components.common.toggle_switch import ToggleSwitch
from pandaplot.gui.core.widget_extension import PWizardPage
from pandaplot.gui.dialogs.chart.wizard_footer import WizardFooter
from pandaplot.gui.dialogs.chart.wizard_step_rail import WizardStepRail
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class ChartLabelsPage(PWizardPage):
    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
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

        left_column = QVBoxLayout()
        content.addLayout(left_column, 1)

        self._title_touched = False
        self._subtitle_touched = False
        self._x_touched = False
        self._y_touched = False

        form = QFormLayout()
        left_column.addLayout(form)

        self.title_edit = QLineEdit()
        self.title_edit.textChanged.connect(lambda: setattr(self, "_title_touched", True))
        form.addRow("Title:", self.title_edit)

        self.subtitle_edit = QLineEdit()
        self.subtitle_edit.textChanged.connect(lambda: setattr(self, "_subtitle_touched", True))
        form.addRow("Subtitle:", self.subtitle_edit)

        self.x_label_edit = QLineEdit()
        self.x_label_edit.textChanged.connect(lambda: setattr(self, "_x_touched", True))
        form.addRow("X-axis label:", self.x_label_edit)

        self.y_label_edit = QLineEdit()
        self.y_label_edit.textChanged.connect(lambda: setattr(self, "_y_touched", True))
        form.addRow("Y-axis label:", self.y_label_edit)

        toggles_card = Card()
        toggles_layout = QGridLayout(toggles_card)
        toggles_layout.addWidget(QLabel("Show legend"), 0, 0)
        self.show_legend_toggle = ToggleSwitch(checked=True)
        toggles_layout.addWidget(self.show_legend_toggle, 0, 1)
        toggles_layout.addWidget(QLabel("Show grid lines"), 1, 0)
        self.show_grid_toggle = ToggleSwitch(checked=True)
        toggles_layout.addWidget(self.show_grid_toggle, 1, 1)
        left_column.addWidget(toggles_card)

        preview_card = Card()
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_container.setLayout(container_layout)
        preview_layout.addWidget(self._preview_container, 1)
        content.addWidget(preview_card, 1)

        self.preview_canvas = None
        self._last_project = None
        self._last_chart_type = "line"
        self._last_series_configs: list[dict] = []
        for widget in (self.title_edit, self.subtitle_edit, self.x_label_edit, self.y_label_edit):
            widget.textChanged.connect(self._refresh_preview_from_cache)
        self.show_legend_toggle.toggled.connect(self._refresh_preview_from_cache)
        self.show_grid_toggle.toggled.connect(self._refresh_preview_from_cache)

        self.footer = WizardFooter(step_number=3, total_steps=3, show_empty_link=False)
        self.footer.backClicked.connect(lambda: self.wizard().back())
        self.footer.finishClicked.connect(lambda: self.wizard().accept())
        self.footer.cancelClicked.connect(lambda: self.wizard().reject())
        outer.addWidget(self.footer)

    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        tokens = theme_manager.get_design_tokens()
        self.step_rail.set_tokens(tokens)
        self.footer.set_tokens(tokens)
        self.show_legend_toggle.set_tokens(tokens)
        self.show_grid_toggle.set_tokens(tokens)

    def set_defaults(self, title: str, x_label: str, y_label: str) -> None:
        """Refresh whichever fields the user hasn't actually edited yet.

        Called every time the wizard's Labels page is entered (not just
        once) -- a field the user has typed into is never touched again
        regardless of what changed elsewhere in the wizard, but an
        untouched field always reflects the current Data-step state (e.g.
        after the user picks a different column for a series). Subtitle has
        no data-derived default, so it's always seeded to "" the same way.
        """
        for edit, touched, value in (
            (self.title_edit, self._title_touched, title),
            (self.subtitle_edit, self._subtitle_touched, ""),
            (self.x_label_edit, self._x_touched, x_label),
            (self.y_label_edit, self._y_touched, y_label),
        ):
            if touched:
                continue
            edit.blockSignals(True)  # noqa: FBT003 - Qt method, no keyword args
            try:
                edit.setText(value)
            finally:
                edit.blockSignals(False)  # noqa: FBT003 - Qt method, no keyword args

    def get_title(self) -> str:
        return self.title_edit.text()

    def get_subtitle(self) -> str:
        return self.subtitle_edit.text()

    def get_x_label(self) -> str:
        return self.x_label_edit.text()

    def get_y_label(self) -> str:
        return self.y_label_edit.text()

    def get_show_legend(self) -> bool:
        return self.show_legend_toggle.isChecked()

    def get_show_grid(self) -> bool:
        return self.show_grid_toggle.isChecked()

    def refresh_preview(self, project, chart_type: str, series_configs: list[dict]) -> None:
        """Re-render the preview from the wizard's current state.

        Called by `ChartWizard` every time the Labels page is entered (with
        the Type/Data steps' actual state), and by this page's own field/
        toggle-change handlers thereafter (re-using the last-seen
        project/chart_type/series_configs, since those three only change via
        this method's own caller).
        """
        from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas
        from pandaplot.gui.dialogs.chart.wizard_preview import render_wizard_preview

        self._last_project = project
        self._last_chart_type = chart_type
        self._last_series_configs = series_configs

        if self.preview_canvas is not None:
            self._preview_container.layout().removeWidget(self.preview_canvas)
            self.preview_canvas.setParent(None)
            self.preview_canvas.deleteLater()

        canvas = ChartCanvas(width=3, height=2.5, dpi=70)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        render_wizard_preview(
            canvas, project, chart_type, series_configs,
            title=self.get_title(), subtitle=self.get_subtitle(),
            x_label=self.get_x_label(), y_label=self.get_y_label(),
            show_legend=self.get_show_legend(), show_grid=self.get_show_grid(),
        )
        self._preview_container.layout().addWidget(canvas)
        self.preview_canvas = canvas

    def _refresh_preview_from_cache(self, *_args) -> None:
        self.refresh_preview(self._last_project, self._last_chart_type, self._last_series_configs)
