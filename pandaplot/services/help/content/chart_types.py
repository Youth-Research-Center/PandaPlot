"""Help topics derived per chart type (filled in by a later task)."""

from pandaplot.models.chart.chart_type import ChartType
from pandaplot.services.help.help_types import HelpTopic

CHART_TYPE_TOPIC_IDS: dict[ChartType, str] = {chart_type: f"charts.{chart_type.value}" for chart_type in ChartType}


def topics() -> list[HelpTopic]:
    """Return the per-chart-type topics.

    Returns:
        The topics (none yet).
    """
    return []
