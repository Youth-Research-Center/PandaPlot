"""Command for applying chart property changes (Apply button)."""

import copy
from dataclasses import asdict
from typing import Any, Callable, Dict, Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items.chart import Chart, DataSeries
from pandaplot.models.state import AppContext


class ApplyChartPropertiesCommand(Command):
    """Command that captures chart state before/after applying property changes."""

    def __init__(self, app_context: AppContext, chart_id: str,
                 apply_fn: Callable[[Chart], None]):
        super().__init__()
        self.app_context = app_context
        self.chart_id = chart_id
        self._apply_fn = apply_fn
        self.old_snapshot: Optional[Dict[str, Any]] = None
        self.new_snapshot: Optional[Dict[str, Any]] = None

    def _find_chart(self) -> Optional[Chart]:
        app_state = self.app_context.get_app_state()
        if not app_state.has_project or not app_state.current_project:
            return None
        return app_state.current_project.find_item(self.chart_id)

    @staticmethod
    def _snapshot_chart(chart: Chart) -> Dict[str, Any]:
        """Capture the mutable chart state that apply_to_chart can change."""
        return {
            'config': copy.deepcopy(chart.config),
            'chart_type': chart.chart_type,
            'name': chart.name,
            'data_series': [asdict(s) for s in chart.data_series],
            'fit_data_styles': [
                {'color': f.color, 'line_width': f.line_width}
                for f in chart.fit_data
            ],
        }

    @staticmethod
    def _restore_snapshot(chart: Chart, snapshot: Dict[str, Any]) -> None:
        """Restore chart state from a snapshot."""
        chart.config = copy.deepcopy(snapshot['config'])
        chart.chart_type = snapshot['chart_type']
        chart.name = snapshot['name']

        # Restore data series
        chart.data_series = [DataSeries(**d) for d in snapshot['data_series']]

        # Restore fit data styles (only mutable style fields)
        for i, fit_style in enumerate(snapshot['fit_data_styles']):
            if i < len(chart.fit_data):
                chart.fit_data[i].color = fit_style['color']
                chart.fit_data[i].line_width = fit_style['line_width']

        chart.update_modified_time()

    def _emit_update(self, chart: Chart) -> None:
        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            'chart_id': self.chart_id,
            'chart': chart,
        })

    @override
    def execute(self) -> bool:
        chart = self._find_chart()
        if not chart or not isinstance(chart, Chart):
            return False

        # Snapshot before applying
        self.old_snapshot = self._snapshot_chart(chart)

        # Apply changes via the provided callback
        self._apply_fn(chart)

        # Snapshot after applying
        self.new_snapshot = self._snapshot_chart(chart)

        self._emit_update(chart)
        return True

    @override
    def undo(self):
        chart = self._find_chart()
        if not chart or self.old_snapshot is None:
            return
        self._restore_snapshot(chart, self.old_snapshot)
        self._emit_update(chart)

    @override
    def redo(self):
        chart = self._find_chart()
        if not chart or self.new_snapshot is None:
            return
        self._restore_snapshot(chart, self.new_snapshot)
        self._emit_update(chart)
