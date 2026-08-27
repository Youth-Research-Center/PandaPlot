"""Command for applying a fit to a chart."""

from typing import Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.state import AppContext

# Maps a short fit-type name to its chart color. `fit_type` from the fit panel is a
# full descriptive string (e.g. "Linear (y = ax + b)"), so lookups use substring
# matching rather than exact-match, mirroring FitService._get_fit_func.
FIT_TYPE_COLORS = {
    "Linear": "#ff0000",       # Red
    "Quadratic": "#00aa00",    # Green
    "Exponential": "#0066cc",  # Blue
    "Power": "#cc00cc",        # Magenta
    "Logarithmic": "#ff6600",  # Orange
    "Custom": "#00cccc",       # Cyan
}


def _resolve_fit_style(fit_type: str) -> tuple[str, str]:
    """Return (short_name, color) for a fit_type string like 'Linear (y = ax + b)'."""
    for short_name, color in FIT_TYPE_COLORS.items():
        if short_name in fit_type:
            return short_name, color
    return fit_type, "#ff0000"


class ApplyFitCommand(Command):
    """Command to apply fitted data to an existing chart."""

    def __init__(
        self,
        app_context: AppContext,
        chart_id: str,
        fit_results,
        source_dataset_id: str,
        source_x_column_id: str,
        source_y_column_id: str,
        source_x_column: str = "",
        source_y_column: str = "",
        label: str = "",
    ):
        super().__init__()

        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.chart_id = chart_id
        self.fit_results = fit_results

        self.source_dataset_id = source_dataset_id
        self.source_x_column_id = source_x_column_id
        self.source_y_column_id = source_y_column_id
        self.source_x_column = source_x_column
        self.source_y_column = source_y_column
        self.label = label

        self.added_index: Optional[int] = None

    def _find_chart(self) -> Optional[Chart]:
        app_state = self.app_context.get_app_state()

        if not app_state.has_project or not app_state.current_project:
            return None

        chart = app_state.current_project.find_item(self.chart_id)

        if not isinstance(chart, Chart):
            return None

        return chart

    @override
    def execute(self) -> bool:
        chart = self._find_chart()

        if chart is None:
            self.logger.warning(
                "ApplyFitCommand.execute: chart '%s' not found or not a Chart",
                self.chart_id,
            )
            self.ui_controller.show_error_message(
                "Apply Fit Error", f"Chart '{self.chart_id}' not found."
            )
            return False

        results = self.fit_results

        short_fit_name, fit_color = _resolve_fit_style(results.fit_type)
        label = self.label or f"{short_fit_name} Fit: ({results.equation})"

        chart.add_fit_data(
            source_dataset_id=self.source_dataset_id,
            source_x_column_id=self.source_x_column_id,
            source_y_column_id=self.source_y_column_id,
            fit_type=results.fit_type,
            x_data=results.x_fit,
            y_data=results.y_fit,
            source_x_column=self.source_x_column,
            source_y_column=self.source_y_column,
            label=label,
            style=FitStyle(color=fit_color, line_style="dashed", line_width=2.0),
            fit_params=results.params,
            fit_stats={
                "r_squared": results.r_squared,
            },
            confidence_lower=results.confidence_lower,
            confidence_upper=results.confidence_upper,
        )

        self.added_index = len(chart.fit_data) - 1

        self.app_context.event_bus.emit(
            ChartEvents.CHART_UPDATED,
            {
                "chart_id": self.chart_id,
                "update_type": "fit_added",
                "chart": chart,
            },
        )

        return True

    @override
    def undo(self):
        chart = self._find_chart()

        if chart is None or self.added_index is None:
            self.logger.warning(
                "ApplyFitCommand.undo: cannot undo for chart '%s' (chart found=%s, added_index set=%s)",
                self.chart_id, chart is not None, self.added_index is not None,
            )
            return

        chart.remove_fit_data(self.added_index)

        self.app_context.event_bus.emit(
            ChartEvents.CHART_UPDATED,
            {
                "chart_id": self.chart_id,
                "update_type": "fit_removed",
                "chart": chart,
            },
        )

    @override
    def redo(self):
        self.execute()

    @override
    def cleanup(self) -> None:
        """Release the insertion-index bookkeeping held for undo once this
        command is dropped from the stacks for good (see Command.cleanup)."""
        self.added_index = None
