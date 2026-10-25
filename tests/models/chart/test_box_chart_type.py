"""Model-level coverage for the Box chart/series type (#399): persistence,
style building and chart-type switching -- the paths a new type picks up
from SERIES_TYPE_SPECS/CHART_TYPE_SPECS without any code of its own."""
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_style import BoxSeriesStyle, HistSeriesStyle
from pandaplot.models.chart.series_style_builder import build_series_style
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart, YAxis


def test_box_series_round_trips_with_its_style():
    chart = Chart(name="Groups", chart_type="box")
    chart.add_data_series(
        dataset_id="ds1", y_column_id="a", label="Group A", series_type=SeriesType.BOX,
        style=BoxSeriesStyle(color="#ff0000", show_outliers=False, notch=True, box_width=0.3),
    )

    restored = Chart.from_dict(chart.to_dict())

    assert restored.chart_type == ChartType.BOX
    (series,) = restored.data_series
    assert series.series_type == SeriesType.BOX
    assert series.style == BoxSeriesStyle(color="#ff0000", show_outliers=False, notch=True, box_width=0.3)


def test_a_series_added_to_a_box_chart_defaults_to_box():
    chart = Chart(name="Groups", chart_type="box")
    series = chart.add_data_series(dataset_id="ds1", y_column_id="a")
    assert series.series_type == SeriesType.BOX
    assert isinstance(series.style, BoxSeriesStyle)


def test_build_series_style_puts_the_color_on_a_box_style():
    style = build_series_style(SeriesType.BOX, color="#00ff00")
    assert isinstance(style, BoxSeriesStyle)
    assert style.color == "#00ff00"


def test_switching_a_histogram_to_box_keeps_the_values_column_and_color():
    """Hist and Box share the same single "values" column (y_column_id), so
    the switch retypes the series without losing its data binding."""
    chart = Chart(name="Dist", chart_type="hist")
    chart.add_data_series(
        dataset_id="ds1", y_column_id="a", series_type=SeriesType.HIST,
        style=HistSeriesStyle(color="#123456"),
    )

    chart.set_chart_type(ChartType.BOX)

    (series,) = chart.data_series
    assert series.series_type == SeriesType.BOX
    assert series.y_column_id == "a"
    assert isinstance(series.style, BoxSeriesStyle)
    assert series.style.color == "#123456"


def test_retyping_a_secondary_axis_series_to_box_moves_it_to_the_primary_axis():
    """Box series can't sit on Y2 (the Data tab hides the control), so a
    retype must not leave an existing Y2 series stranded there."""
    chart = Chart(name="Dist", chart_type="hist")
    chart.add_data_series(dataset_id="ds1", y_column_id="a", series_type=SeriesType.HIST,
                          style=HistSeriesStyle(), y_axis=YAxis.SECONDARY)

    chart.set_chart_type(ChartType.BOX)

    assert chart.data_series[0].y_axis == YAxis.PRIMARY
