"""Shared construction of chart series from role-keyed column configs.

Used by every entry point that turns a "which dataset, which columns" choice
(the chart wizard, the Add Series dialog) into a `DataSeries`, so they all
build identical series.
"""

from collections.abc import Mapping

from pandaplot.models.chart.chart_type_spec import get_chart_type_spec
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style_builder import build_series_style
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import DataSeries, YAxis
from pandaplot.models.project.project import Project


def dataset_columns(project: Project, dataset_id: str) -> list[tuple[str, str]]:
    """Return (column_id, column name) pairs for one dataset.

    Args:
        project: The project holding the dataset.
        dataset_id: Id of the dataset.

    Returns:
        The column pairs, or an empty list if the item is missing, is not a
        dataset, or has no data loaded.
    """
    dataset = project.find_item(dataset_id)
    if not isinstance(dataset, Dataset) or dataset.data is None:
        return []
    return [(dataset.column_id(name) or "", name) for name in dataset.data.columns]


def _default_series_label(project: Project, config: Mapping[str, str | bool]) -> str:
    """Default label "{dataset name}:{Y column name}", or just the dataset name.

    Falls back to the dataset id if the dataset is missing, and to the bare
    dataset name if the Y column cannot be resolved.
    """
    dataset_id = str(config.get("dataset_id", ""))
    dataset = project.find_item(dataset_id)
    dataset_name = dataset.name if isinstance(dataset, Dataset) else dataset_id
    y_column_id = str(config.get("y_column_id", ""))
    y_column_name = ""
    if isinstance(dataset, Dataset) and y_column_id:
        y_column_name = dataset.column_name(y_column_id) or ""
    if y_column_name:
        return f"{dataset_name}:{y_column_name}"
    return dataset_name


def build_series_from_config(project: Project, chart_type: str, config: Mapping[str, str | bool], *, color: str) -> DataSeries:
    """Build a `DataSeries` for `chart_type` from a role-keyed column config.

    The series is not added to any chart. Missing config keys default to an
    empty string, except `error_symmetric`, which defaults to True.

    Args:
        project: The project used to resolve the default label.
        chart_type: Chart type the series is for; selects the series type.
        config: Column ids keyed by role (`dataset_id`, `x_column_id`,
            `y_column_id`, error, u/v/w, magnitude, z and label columns).
        color: Series color applied to the style.

    Returns:
        The new series. Box series are always placed on the primary Y axis.
    """
    series_type = get_chart_type_spec(chart_type).default_series_type
    style = build_series_style(
        series_type,
        color=color,
        error_bars=ErrorBarConfig(
            x_error_column_id=str(config.get("x_error_column_id", "")),
            y_error_column_id=str(config.get("y_error_column_id", "")),
            x_error_minus_column_id=str(config.get("x_error_minus_column_id", "")),
            y_error_minus_column_id=str(config.get("y_error_minus_column_id", "")),
            error_symmetric=bool(config.get("error_symmetric", True)),
        ),
        u_column_id=str(config.get("u_column_id", "")),
        v_column_id=str(config.get("v_column_id", "")),
        w_column_id=str(config.get("w_column_id", "")),
        magnitude_column_id=str(config.get("magnitude_column_id", "")),
        z_column_id=str(config.get("z_column_id", "")),
        label_column_id=str(config.get("label_column_id", "")),
    )
    series = DataSeries(
        dataset_id=str(config.get("dataset_id", "")),
        x_column_id=str(config.get("x_column_id", "")),
        y_column_id=str(config.get("y_column_id", "")),
        label=_default_series_label(project, config),
        series_type=series_type,
        style=style,
    )
    if series_type == SeriesType.BOX:
        series.y_axis = YAxis.PRIMARY
    return series
