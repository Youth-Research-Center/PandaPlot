"""Shared tab/chart-context tracking for sidebar panels scoped to a chart
tab's current chart and selected series/fit source.

Used by ChartAnalysisPanel, ChartSignalAnalysisPanel, and ChartTransformPanel
-- see docs/superpowers/specs/2026-09-10-chart-panel-boilerplate-extraction-
design.md for why this was extracted (#284).
"""

from typing import Optional

from pandaplot.gui.components.sidebar.chart.series_source_picker import (
    find_series_fit_combo_index,
)
from pandaplot.models.events import ChartEvents, ProjectEvents, UIEvents
from pandaplot.models.project.items.chart import Chart


class ChartSeriesContextMixin:
    """Mixin providing current_chart/current_chart_id tracking plus the
    TAB_CHANGED/CHART_UPDATED/SERIES_SELECTED/PROJECT_ITEM_* handlers shared
    by every sidebar panel scoped to a chart tab's current chart and
    selected series/fit source.

    Subclasses must, before `_initialize()` runs:
    - set `self.current_chart: Optional[Chart] = None`
    - set `self.current_chart_id: Optional[str] = None`
    - have `self.source_combo` (a QComboBox populated via
      series_source_picker.populate_series_fit_sources) constructed
    - call `self.setup_chart_series_context_subscriptions()` from their own
      `setup_event_subscriptions()`
    - implement `_populate_sources()` -- called whenever current_chart/
      current_chart_id are (re)established (tab switch, or this chart's
      own CHART_UPDATED)

    Subclasses may override `_refresh_chart_references()` -- called when a
    *different* chart's metadata changes (PROJECT_ITEM_ADDED/REMOVED/
    RENAMED/MOVED, or another chart's own CHART_UPDATED) in a way that
    could affect a chart reference this panel shows elsewhere (e.g. a
    "plot result on" destination combo). Default is a no-op.
    """

    current_chart: Optional[Chart]
    current_chart_id: Optional[str]

    def setup_chart_series_context_subscriptions(self) -> None:
        self.subscribe_to_event(UIEvents.TAB_CHANGED, self._on_tab_changed)
        self.subscribe_to_event(ChartEvents.CHART_UPDATED, self._on_chart_updated)
        self.subscribe_to_event(ChartEvents.SERIES_SELECTED, self._on_series_selected_event)
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_ADDED, self._on_chart_list_changed)
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_REMOVED, self._on_chart_list_changed)
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_RENAMED, self._on_chart_list_changed)
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_MOVED, self._on_chart_list_changed)

    def _populate_sources(self) -> None:
        raise NotImplementedError

    def _refresh_chart_references(self) -> None:
        pass

    def _resolve_updated_chart(self, event_data: dict) -> Optional[Chart]:
        """Resolve the chart a CHART_UPDATED event refers to, or None if it
        doesn't resolve to a real Chart. Some emitters (e.g.
        ChartPropertiesPanel's live-edit publish, which fires on every
        properties-tab change including a chart-type retype) only send
        chart_id, not the Chart object itself -- resolve it from the
        project so callers still react to those."""
        chart = event_data.get("chart")
        if chart is not None:
            return chart if isinstance(chart, Chart) else None
        chart_id = event_data.get("chart_id")
        if not chart_id:
            return None
        project = self.app_context.get_app_state().current_project
        found = project.find_item(chart_id) if project else None
        return found if isinstance(found, Chart) else None

    def _on_series_selected_event(self, event_data: dict) -> None:
        """Clicking a series/fit on the chart canvas or its legend also
        selects it here, so switching from "look at it" to acting on it
        doesn't require re-finding the same entry in this combo."""
        chart_id = event_data.get("chart_id")
        if self.current_chart_id is None or chart_id != self.current_chart_id:
            return
        kind = event_data.get("kind")
        index = event_data.get("index")
        if kind is None or index is None:
            return
        combo_index = find_series_fit_combo_index(self.source_combo, kind, index)
        if combo_index >= 0:
            self.source_combo.setCurrentIndex(combo_index)

    def _on_tab_changed(self, event_data: dict) -> None:
        if event_data.get("tab_type") == "chart":
            chart_id = event_data.get("tab_id")
            self.current_chart_id = chart_id
            project = self.app_context.get_app_state().current_project
            chart = project.find_item(chart_id) if project and chart_id else None
            self.current_chart = chart if isinstance(chart, Chart) else None
        else:
            self.current_chart = None
            self.current_chart_id = None
        self._populate_sources()

    def _on_chart_updated(self, event_data: dict) -> None:
        chart = self._resolve_updated_chart(event_data)
        if not chart or (self.current_chart_id and chart.id != self.current_chart_id):
            # A different chart's own update (rename/retype/etc.) doesn't
            # change this panel's context, but can change a chart
            # reference shown elsewhere in the panel -- refresh that
            # without disturbing the current chart/source selection.
            if chart is not None:
                self._refresh_chart_references()
            return
        self._apply_chart_update(chart, event_data)

    def _apply_chart_update(self, chart: Chart, event_data: dict) -> None:
        """Hook for _on_chart_updated(), called once `chart` has resolved
        to this panel's own current chart (or is about to become it).
        Default: adopt it and repopulate. Override to interpose extra
        logic (e.g. deferring while a background dispatch is in flight)
        before calling super()."""
        self.current_chart = chart
        self.current_chart_id = chart.id
        self._populate_sources()

    def _on_chart_list_changed(self, event_data: dict) -> None:
        """A chart added/renamed/removed/moved anywhere in the project can
        change a chart reference shown elsewhere in the panel -- refresh
        without disturbing the current chart/source selection."""
        self._refresh_chart_references()
