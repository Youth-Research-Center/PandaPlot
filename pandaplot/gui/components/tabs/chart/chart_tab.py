"""Chart tab widget for displaying and editing charts."""

from typing import override

from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events import ChartEvents, FitEvents, UIEvents
from pandaplot.models.project.items import Chart
from pandaplot.models.state.app_context import AppContext


class ChartTab(PWidget):
    """
    Main chart tab widget that contains the chart editor.
    """

    def __init__(self, app_context: AppContext, chart: Chart, parent: QWidget):
        super().__init__(app_context=app_context, parent=parent)
        self.chart = chart
        self._initialize()

    @override
    def _init_ui(self):
        """Set up the chart tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create chart editor
        self.chart_editor = ChartEditorWidget(app_context=self.app_context, chart=self.chart, parent=self)

        layout.addWidget(self.chart_editor)

    @override
    def _apply_theme(self):
        pass

    def setup_event_subscriptions(self):
        """Set up event subscriptions for tab title changes and chart updates."""
        self.subscribe_to_event(
            UIEvents.TAB_TITLE_CHANGED, self.on_tab_title_changed)
        self.subscribe_to_event(
            ChartEvents.CHART_UPDATED, self.on_chart_updated)
        self.subscribe_to_event(FitEvents.FIT_APPLIED, self.on_fit_applied)

    def on_tab_title_changed(self, event_data: dict):
        """Handle tab title change events."""
        # Check if this title change is for our chart
        chart_name = event_data.get('new_title')
        if chart_name and event_data.get('tab_type') == 'chart':
            # This is handled by the tab container - we just need to acknowledge the event
            pass

    def on_chart_updated(self, event_data: dict):
        """Handle chart update events from other components."""
        updated_chart_id = event_data.get('chart_id')

        # Only respond if this is our chart
        if updated_chart_id == self.chart.id:
            # Refresh the chart display
            if hasattr(self.chart_editor, 'refresh_chart'):
                self.chart_editor.refresh_chart()
                self.logger.debug(
                    "ChartTab refreshed for chart %s", self.chart.name)

    def on_fit_applied(self, event_data: dict):
        """Handle fit applied events to add fit curves to the chart."""
        fit_chart_id = event_data.get('chart_id')

        # Only respond if this is our chart
        if fit_chart_id == self.chart.id:
            fit_results = event_data.get('fit_results', {})
            fit_type = fit_results.get('fit_type', 'Unknown')
            source_dataset_name = event_data.get('dataset_name', 'Unknown')

            # Get the source dataset info from the fit results
            source_dataset_id = fit_results.get('source_dataset_id', '')
            source_x_column = fit_results.get('source_x_column', '')
            source_y_column = fit_results.get('source_y_column', '')

            # Generate unique color for fit line based on fit type
            fit_colors = {
                'Linear': '#ff0000',      # Red
                'Polynomial': '#00aa00',  # Green
                'Exponential': '#0066cc',  # Blue
                'Logarithmic': '#ff6600',  # Orange
                'Power': '#cc00cc',       # Magenta
                'Gaussian': '#00cccc',    # Cyan
            }
            fit_color = fit_colors.get(fit_type, '#ff0000')  # Default to red

            # Add fit data directly to the chart
            import numpy as np
            x_fit = np.array(fit_results.get('x_fit', []))
            y_fit = np.array(fit_results.get('y_fit', []))

            fit_params = fit_results.get('fit_params', {})
            fit_stats = fit_results.get('fit_stats', {})

            self.chart.add_fit_data(
                source_dataset_id=source_dataset_id,
                source_x_column=source_x_column,
                source_y_column=source_y_column,
                fit_type=fit_type,
                x_data=x_fit,
                y_data=y_fit,
                label=f"{fit_type} Fit ({source_dataset_name})",
                color=fit_color,
                line_style="dashed",
                line_width=2.0,
                fit_params=fit_params,
                fit_stats=fit_stats
            )

            # Refresh the chart display to show the new fit
            if hasattr(self.chart_editor, 'refresh_chart'):
                self.chart_editor.refresh_chart()

            # Publish chart updated event to notify other components
            self.publish_event(ChartEvents.CHART_UPDATED, {
                'chart_id': self.chart.id,
                'chart': self.chart,
                'update_type': 'fit_added'
            })

    def get_tab_title(self) -> str:
        """Get the tab title."""
        return f"📈 {self.chart.name}"

    def get_chart(self) -> Chart:
        """Get the chart object."""
        return self.chart

    def refresh_chart(self):
        """Refresh the chart display when properties are updated externally."""
        if hasattr(self.chart_editor, 'refresh_chart'):
            self.chart_editor.refresh_chart()
