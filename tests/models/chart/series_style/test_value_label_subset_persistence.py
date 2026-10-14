"""Tests that value-label subset settings survive save/load and retyping."""
import json

from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart


def _chart_with_line_series() -> Chart:
    chart = Chart(name="test", chart_type="line")
    chart.add_data_series("dataset-1", label="s")
    return chart


def test_subset_settings_survive_save_and_load():
    chart = _chart_with_line_series()
    style = chart.data_series[0].style
    style.value_label_subset_mode = "custom"
    style.value_label_custom_indices = [0, 3, 5]

    loaded = Chart.from_dict(json.loads(json.dumps(chart.to_dict())))

    loaded_style = loaded.data_series[0].style
    assert loaded_style.value_label_subset_mode == "custom"
    assert loaded_style.value_label_custom_indices == [0, 3, 5]


def test_old_saved_style_without_subset_fields_uses_defaults():
    chart = _chart_with_line_series()
    data = chart.to_dict()
    del data["data_series"][0]["style"]["value_label_subset_mode"]
    del data["data_series"][0]["style"]["value_label_custom_indices"]

    loaded = Chart.from_dict(data)

    loaded_style = loaded.data_series[0].style
    assert loaded_style.value_label_subset_mode == "all"
    assert loaded_style.value_label_custom_indices == []


def test_retype_line_to_scatter_keeps_subset_settings_as_independent_copy():
    chart = _chart_with_line_series()
    old_style = chart.data_series[0].style
    old_style.value_label_subset_mode = "custom"
    old_style.value_label_custom_indices = [1, 2]

    chart.retype_series(0, SeriesType.SCATTER)

    new_style = chart.data_series[0].style
    assert new_style.value_label_subset_mode == "custom"
    assert new_style.value_label_custom_indices == [1, 2]
    new_style.value_label_custom_indices.append(9)
    assert old_style.value_label_custom_indices == [1, 2]