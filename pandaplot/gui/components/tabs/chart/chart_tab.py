"""Chart tab widget for displaying and editing charts."""

from typing import override

from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events import ChartEvents
from pandaplot.models.events.event_types import DatasetEvents, ProjectEvents
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
            ProjectEvents.PROJECT_ITEM_RENAMED, self.on_chart_renamed)
        self.subscribe_to_event(
            ChartEvents.CHART_UPDATED, self.on_chart_updated)
        # Charts read their series data live from the source datasets, so any
        # change to a dataset this chart plots (cell edits, added/removed
        # rows or columns, imports, analysis columns) must re-render the
        # chart. DATASET_CHANGED is the generic parent of all those specific
        # dataset events (see EventHierarchy), so one subscription covers them.
        self.subscribe_to_event(
            DatasetEvents.DATASET_CHANGED, self.on_dataset_changed)

    def on_chart_renamed(self, event_data: dict):
        """Update the tab title when the underlying chart item is renamed."""
        if event_data.get("item_id") == self.chart.id:
            self.refresh_tab_title()

    def refresh_tab_title(self):
        """Push the current tab title up to the tab container."""
        parent_container = self.parent()
        while parent_container is not None and not hasattr(parent_container, "update_tab_title"):
            parent_container = parent_container.parent()
        if parent_container:
            update_fn = getattr(parent_container, "update_tab_title", None)
            if callable(update_fn):
                try:
                    update_fn(self, self.get_tab_title())
                except Exception:
                    pass

    def on_chart_updated(self, event_data: dict):
        """Handle chart update events from other components."""
        updated_chart_id = event_data.get("chart_id")

        # Only respond if this is our chart
        if updated_chart_id == self.chart.id:
            self._refresh_chart_editor()

    def on_dataset_changed(self, event_data: dict):
        """Refresh the chart when one of its source datasets changes."""
        changed_dataset_id = event_data.get("dataset_id")
        if changed_dataset_id is None:
            return

        # Only re-render if this chart actually plots the changed dataset.
        if changed_dataset_id in self.chart.get_all_datasets():
            self._refresh_chart_editor()

    def _refresh_chart_editor(self):
        """Refresh the chart editor's preview, guarding against a deleted widget."""
        if hasattr(self, "chart_editor") and isValid(self.chart_editor):
            try:
                self.chart_editor.refresh_chart()
                self.logger.debug(
                    "ChartTab refreshed for chart %s", self.chart.name)
            except RuntimeError as e:
                # Widget was deleted during callback
                self.logger.debug(f"Chart editor deleted during update: {e}")

    def get_tab_title(self) -> str:
        """Get the tab title."""
        return f"📈 {self.chart.name}"

    def get_tab_data(self) -> dict:
        """Identify this tab to TabContainer for session/event bookkeeping."""
        return {"type": "chart", "id": self.chart.id}

    def get_chart(self) -> Chart:
        """Get the chart object."""
        return self.chart
