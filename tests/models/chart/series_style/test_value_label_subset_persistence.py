"""Tests that the value-label subset setting survives save/load and retyping."""
import json

from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart


def _chart_with_line_series() -> Chart:
    chart = Chart(name="test", chart_type="line")
    chart.add_data_series("dataset-1", label="s")
    return chart


def test_subset_mode_survives_save_and_load():
    chart = _chart_with_line_series()
    chart.data_series[0].style.value_label_subset_mode = "max"

    loaded = Chart.from_dict(json.loads(json.dumps(chart.to_dict())))

    assert loaded.data_series[0].style.value_label_subset_mode == "max"


def test_old_saved_style_without_subset_field_uses_default():
    chart = _chart_with_line_series()
    data = chart.to_dict()
    del data["data_series"][0]["style"]["value_label_subset_mode"]

    loaded = Chart.from_dict(data)

    assert loaded.data_series[0].style.value_label_subset_mode == "all"


def test_retype_line_to_scatter_keeps_subset_mode():
    chart = _chart_with_line_series()
    chart.data_series[0].style.value_label_subset_mode = "extremes"

    chart.retype_series(0, SeriesType.SCATTER)

    assert chart.data_series[0].style.value_label_subset_mode == "extremes"


def test_invalid_subset_mode_falls_back_to_all():
    from pandaplot.models.chart.series_style.line import LineSeriesStyle
    from pandaplot.models.chart.value_label_subset import ValueLabelSubset

    assert LineSeriesStyle(value_label_subset_mode="typo").value_label_subset_mode is ValueLabelSubset.ALL
    assert LineSeriesStyle(value_label_subset_mode="max").value_label_subset_mode is ValueLabelSubset.MAX

