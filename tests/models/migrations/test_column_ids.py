"""Tests for the cross-item column-id backfill migration.

This is the same logic that used to live as
ProjectDataManager._migrate_series_column_ids — moved here as the first
registered cross-item migration (see registry.py). It resolves a chart
series/fit's dataset column *name* reference to a stable *id*, which
requires looking up the series' source Dataset — data that isn't
available from the chart's own raw dict in isolation, hence "cross-item"
rather than a per-item dict migration.
"""
import pandas as pd

from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.migrations.cross_item.column_ids import migrate_column_ids
from pandaplot.models.project.items.chart import Chart, DataSeries
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project


def _project_with_dataset_and_series(x_column: str, y_column: str) -> tuple[Project, Chart, Dataset]:
    project = Project(name="Test Project")
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({x_column: [1, 2], y_column: [3, 4]}))
    project.add_item(dataset)

    chart = Chart(id="chart-1", name="Chart", chart_type="line")
    chart.data_series.append(DataSeries(dataset_id="ds-1", x_column=x_column, y_column=y_column))
    project.add_item(chart)

    return project, chart, dataset


def test_backfills_series_column_ids_from_names():
    project, chart, dataset = _project_with_dataset_and_series("x", "y")

    migrate_column_ids(project)

    series = chart.data_series[0]
    assert series.x_column_id == dataset.column_id("x")
    assert series.y_column_id == dataset.column_id("y")


def test_leaves_unmatched_column_names_without_an_id():
    project, chart, _dataset = _project_with_dataset_and_series("x", "y")
    chart.data_series[0].x_column = "not_a_real_column"

    migrate_column_ids(project)

    assert chart.data_series[0].x_column_id == ""


def test_backfills_fit_column_ids_from_names():
    project = Project(name="Test Project")
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"x": [1, 2], "y": [3, 4]}))
    project.add_item(dataset)

    chart = Chart(id="chart-1", name="Chart", chart_type="line")
    chart.add_fit_series(
        source_dataset_id="ds-1",
        x_data=pd.Series([1, 2]).to_numpy(),
        y_data=pd.Series([3, 4]).to_numpy(),
        label="fit",
        style=FitStyle(fit_type="linear"),
        source_x_column="x",
        source_y_column="y",
    )
    project.add_item(chart)

    migrate_column_ids(project)

    fit = chart.fit_data[0]
    assert fit.x_column_id == dataset.column_id("x")
    assert fit.y_column_id == dataset.column_id("y")


def test_ignores_non_chart_items():
    project = Project(name="Test Project")
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"x": [1]}))
    project.add_item(dataset)

    migrate_column_ids(project)  # must not raise
