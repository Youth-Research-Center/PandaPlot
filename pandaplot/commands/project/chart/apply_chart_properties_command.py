"""Command for applying chart property changes (Apply button)."""

from typing import Any, Callable, Dict, Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items.chart import (
    Chart,
    restore_chart_state,
    snapshot_chart_state,
)
from pandaplot.models.state import AppContext


class ApplyChartPropertiesCommand(Command):
    """Command that captures chart state before/after applying property changes."""

    def __init__(self, app_context: AppContext, chart_id: str,
                 apply_fn: Callable[[Chart], None],
                 old_snapshot: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.chart_id = chart_id
        self._apply_fn = apply_fn
        # Baseline for undo. The panel edits the chart live, so the state at
        # execute() time already contains the user's changes; callers pass the
        # snapshot taken when the chart was loaded into the panel.
        self.old_snapshot: Optional[Dict[str, Any]] = old_snapshot
        self.new_snapshot: Optional[Dict[str, Any]] = None

    def _find_chart(self) -> Optional[Chart]:
        app_state = self.app_context.get_app_state()
        if not app_state.has_project or not app_state.current_project:
            return None
        return app_state.current_project.find_item(self.chart_id)

    def _emit_update(self, chart: Chart) -> None:
        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "chart": chart,
        })

    @override
    def execute(self) -> bool:
        chart = self._find_chart()
        if not chart or not isinstance(chart, Chart):
            self.logger.warning(
                "ApplyChartPropertiesCommand.execute: chart '%s' not found or not a Chart (got %s)",
                self.chart_id, type(chart).__name__ if chart else None,
            )
            self.ui_controller.show_error_message(
                "Apply Chart Properties Error", f"Chart '{self.chart_id}' not found."
            )
            return False

        if self.old_snapshot is None:
            self.old_snapshot = snapshot_chart_state(chart)

        # Apply changes via the provided callback
        self._apply_fn(chart)

        # Snapshot after applying
        self.new_snapshot = snapshot_chart_state(chart)

        self._emit_update(chart)
        return True

    @override
    def undo(self):
        chart = self._find_chart()
        if not chart or self.old_snapshot is None:
            self.logger.warning(
                "ApplyChartPropertiesCommand.undo: cannot undo for chart '%s' (chart found=%s, old_snapshot set=%s)",
                self.chart_id, chart is not None, self.old_snapshot is not None,
            )
            return
        restore_chart_state(chart, self.old_snapshot)
        self._emit_update(chart)

    @override
    def redo(self):
        chart = self._find_chart()
        if not chart or self.new_snapshot is None:
            self.logger.warning(
                "ApplyChartPropertiesCommand.redo: cannot redo for chart '%s' (chart found=%s, new_snapshot set=%s)",
                self.chart_id, chart is not None, self.new_snapshot is not None,
            )
            return
        restore_chart_state(chart, self.new_snapshot)
        self._emit_update(chart)
