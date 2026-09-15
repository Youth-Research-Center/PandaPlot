"""Shared chart lookup for chart commands."""

import logging
from typing import Optional

from pandaplot.commands.project.current_project import get_current_project
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.state import AppContext

logger = logging.getLogger(__name__)


class ChartFinder:
    """Resolves a chart by id from the current project.

    Used by chart commands to look up the chart they operate on before
    execute()/undo()/redo(). A resolved item that isn't a Chart logs a
    warning rather than failing silently, since it usually means the
    stored chart_id is stale or wrong rather than a legitimate "no
    project open" case.
    """

    def __init__(self, app_context: AppContext):
        self.app_context = app_context

    def find(self, chart_id: str) -> Optional[Chart]:
        project = get_current_project(self.app_context)
        if project is None:
            return None

        item = project.find_item(chart_id)
        if item is None:
            return None

        if not isinstance(item, Chart):
            logger.warning(
                "ChartFinder: item '%s' is not a Chart (got %s)",
                chart_id, type(item).__name__,
            )
            return None

        return item
