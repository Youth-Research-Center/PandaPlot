"""A line/scatter series' optional twin Y column (#402): a second value column
for the same X, drawn on the Y axis opposite the series' own `y_axis`."""
import json

import pandas as pd
import pytest

from pandaplot.models.chart.series_style import BarSeriesStyle, LineSeriesStyle, ScatterSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, DataSeries, YAxis, assign_series_column_ids
from pandaplot.models.project.project import Project


def test_supports_twin_y_column_is_true_only_for_line_and_scatter():
    supported = {t for t, spec in SERIES_TYPE_SPECS.items() if spec.supports_twin_y_column}
    assert supported == {SeriesType.LINE, SeriesType.SCATTER}


def test_spec_flag_matches_the_style_classes_that_declare_the_field():
    for series_type, spec in SERIES_TYPE_SPECS.items():
        assert hasattr(spec.style_cls(), "twin_y_column_id") is spec.supports_twin_y_column, series_type


def test_series_without_a_twin_y_column_reports_none():
    series = DataSeries(dataset_id="ds", y_column_id="y")
    assert series.has_twin_y_column is False
    assert series.twin_y_axis is None
    assert series.uses_secondary_y_axis is False


@pytest.mark.parametrize(("y_axis", "twin_axis"), [
    (YAxis.PRIMARY, YAxis.SECONDARY),
    (YAxis.SECONDARY, YAxis.PRIMARY),
])
def test_twin_y_column_plots_on_the_opposite_axis(y_axis, twin_axis):
    series = DataSeries(dataset_id="ds", y_column_id="y", y_axis=y_axis,
                        style=LineSeriesStyle(twin_y_column_id="twin"))
    assert series.has_twin_y_column is True
    assert series.twin_y_axis == twin_axis
    assert series.uses_secondary_y_axis is True


def test_twin_y_column_round_trips_through_json():
    chart = Chart(name="C")
    chart.add_data_series("ds", x_column_id="x", y_column_id="y", y_axis=YAxis.SECONDARY,
                          series_type=SeriesType.SCATTER,
                          style=ScatterSeriesStyle(twin_y_column_id="twin", twin_y_column="pressure"))

    restored = Chart.from_dict(json.loads(json.dumps(chart.to_dict())))

    series = restored.data_series[0]
    assert series.style == chart.data_series[0].style
    assert series.style.twin_y_column_id == "twin"
    assert series.style.twin_y_column == "pressure"
    assert series.twin_y_axis == YAxis.PRIMARY


def test_a_saved_style_without_the_twin_keys_loads_with_no_twin_column():
    chart = Chart(name="C")
    chart.add_data_series("ds", x_column_id="x", y_column_id="y")
    raw = chart.to_dict()
    del raw["data_series"][0]["style"]["twin_y_column_id"]
    del raw["data_series"][0]["style"]["twin_y_column"]

    restored = Chart.from_dict(raw)

    assert restored.data_series[0].has_twin_y_column is False


def test_retype_line_to_scatter_carries_the_twin_y_column():
    chart = Chart(name="C")
    chart.add_data_series("ds", x_column_id="x", y_column_id="y",
                          style=LineSeriesStyle(twin_y_column_id="twin", twin_y_column="pressure"))

    chart.retype_series(0, SeriesType.SCATTER)

    style = chart.data_series[0].style
    assert isinstance(style, ScatterSeriesStyle)
    assert (style.twin_y_column_id, style.twin_y_column) == ("twin", "pressure")


def test_retype_to_bar_drops_the_twin_y_column():
    chart = Chart(name="C")
    chart.add_data_series("ds", x_column_id="x", y_column_id="y",
                          style=LineSeriesStyle(twin_y_column_id="twin"))

    chart.retype_series(0, SeriesType.BAR)

    series = chart.data_series[0]
    assert isinstance(series.style, BarSeriesStyle)
    assert series.has_twin_y_column is False
    assert series.uses_secondary_y_axis is False


def test_assign_series_column_ids_resolves_the_twin_y_column_name():
    dataset = Dataset(name="ds", data=pd.DataFrame({"t": [1], "temp": [2], "pressure": [3]}))
    series = DataSeries(dataset_id=dataset.id, x_column="t", y_column="temp",
                        style=LineSeriesStyle(twin_y_column="pressure"))

    assign_series_column_ids(series, dataset)

    assert series.style.twin_y_column_id == dataset.column_id("pressure")


def test_search_matches_the_twin_y_column_name():
    project = Project(name="P")
    dataset = Dataset(name="ds", data=pd.DataFrame({"t": [1], "temp": [2], "pressure": [3]}))
    project.add_item(dataset)
    chart = Chart(name="C")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("t"), y_column_id=dataset.column_id("temp"),
                          label="", style=LineSeriesStyle(twin_y_column_id=dataset.column_id("pressure")))

    assert chart.search_chart("pressure", project) is True
