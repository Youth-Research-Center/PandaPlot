"""Tests that the value-label arrow styling (#504) survives save/load and retyping,
and that invalid saved values fall back to the historical look."""
import json

import pytest

from pandaplot.models.chart.series_style import LineSeriesStyle, ScatterSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.value_label_arrow import ValueLabelArrowLineStyle, ValueLabelArrowStyle
from pandaplot.models.project.items.chart import Chart

ARROW_FIELDS = (
    "value_label_arrow_style", "value_label_arrow_color",
    "value_label_arrow_width", "value_label_arrow_line_style",
)

STYLED = {
    "value_label_arrow_style": ValueLabelArrowStyle.FILLED_ARROW,
    "value_label_arrow_color": "#2ca02c",
    "value_label_arrow_width": 2.5,
    "value_label_arrow_line_style": ValueLabelArrowLineStyle.DASHED,
}


def _chart(chart_type: str) -> Chart:
    chart = Chart(name="test", chart_type=chart_type)
    chart.add_data_series("dataset-1", label="s")
    return chart


def _round_trip(chart: Chart) -> Chart:
    return Chart.from_dict(json.loads(json.dumps(chart.to_dict())))


@pytest.mark.parametrize("chart_type", ["line", "scatter"])
def test_arrow_styling_survives_save_and_load(chart_type):
    chart = _chart(chart_type)
    for name, value in STYLED.items():
        setattr(chart.data_series[0].style, name, value)

    style = _round_trip(chart).data_series[0].style

    for name, value in STYLED.items():
        assert getattr(style, name) == value, name
    assert isinstance(style.value_label_arrow_style, ValueLabelArrowStyle)
    assert isinstance(style.value_label_arrow_line_style, ValueLabelArrowLineStyle)


@pytest.mark.parametrize("chart_type", ["line", "scatter"])
def test_saved_arrow_styling_is_stored_as_plain_json_strings(chart_type):
    chart = _chart(chart_type)
    for name, value in STYLED.items():
        setattr(chart.data_series[0].style, name, value)

    saved = json.loads(json.dumps(chart.to_dict()))["data_series"][0]["style"]

    assert saved["value_label_arrow_style"] == "filled_arrow"
    assert saved["value_label_arrow_line_style"] == "dashed"
    assert saved["value_label_arrow_color"] == "#2ca02c"
    assert saved["value_label_arrow_width"] == 2.5


@pytest.mark.parametrize("chart_type", ["line", "scatter"])
def test_empty_arrow_color_meaning_match_the_label_survives_save_and_load(chart_type):
    chart = _chart(chart_type)
    chart.data_series[0].style.value_label_arrow_color = ""

    assert _round_trip(chart).data_series[0].style.value_label_arrow_color == ""


@pytest.mark.parametrize("chart_type", ["line", "scatter"])
def test_project_saved_before_arrow_styling_keeps_the_historical_look(chart_type):
    chart = _chart(chart_type)
    chart.data_series[0].style.value_label_show_arrow = True
    data = chart.to_dict()
    for name in ARROW_FIELDS:
        del data["data_series"][0]["style"][name]

    style = Chart.from_dict(data).data_series[0].style

    assert style.value_label_show_arrow is True
    assert style.value_label_arrow_style is ValueLabelArrowStyle.LINE
    assert style.value_label_arrow_color == "#000000"
    assert style.value_label_arrow_width == 1.0
    assert style.value_label_arrow_line_style is ValueLabelArrowLineStyle.SOLID


@pytest.mark.parametrize("style_cls", [LineSeriesStyle, ScatterSeriesStyle])
@pytest.mark.parametrize(
    ("field", "invalid", "expected"),
    [
        ("value_label_arrow_style", "typo", ValueLabelArrowStyle.LINE),
        ("value_label_arrow_style", None, ValueLabelArrowStyle.LINE),
        ("value_label_arrow_line_style", "wiggly", ValueLabelArrowLineStyle.SOLID),
        ("value_label_arrow_line_style", "none", ValueLabelArrowLineStyle.SOLID),
        ("value_label_arrow_color", None, "#000000"),
        ("value_label_arrow_color", 7, "#000000"),
        ("value_label_arrow_width", float("nan"), 1.0),
        ("value_label_arrow_width", float("inf"), 1.0),
        ("value_label_arrow_width", 0, 1.0),
        ("value_label_arrow_width", -2.0, 1.0),
        ("value_label_arrow_width", "thick", 1.0),
        ("value_label_arrow_width", None, 1.0),
        ("value_label_arrow_width", 10**400, 1.0),
        ("value_label_arrow_width", 3, 3.0),
    ],
)
def test_invalid_arrow_values_fall_back_to_defaults(style_cls, field, invalid, expected):
    style = style_cls(**{field: invalid})

    assert getattr(style, field) == expected


@pytest.mark.parametrize("style_cls", [LineSeriesStyle, ScatterSeriesStyle])
def test_valid_arrow_values_are_kept(style_cls):
    style = style_cls(**STYLED)

    for name, value in STYLED.items():
        assert getattr(style, name) == value, name
    assert style.value_label_arrow_width == 2.5


@pytest.mark.parametrize("style_cls", [LineSeriesStyle, ScatterSeriesStyle])
def test_arrow_values_given_as_plain_strings_become_enum_members(style_cls):
    style = style_cls(value_label_arrow_style="arrow", value_label_arrow_line_style="dotted")

    assert style.value_label_arrow_style is ValueLabelArrowStyle.ARROW
    assert style.value_label_arrow_line_style is ValueLabelArrowLineStyle.DOTTED


def test_invalid_saved_arrow_values_load_as_defaults():
    chart = _chart("line")
    data = chart.to_dict()
    saved_style = data["data_series"][0]["style"]
    saved_style.update(
        value_label_arrow_style="typo", value_label_arrow_line_style="wiggly",
        value_label_arrow_color=None, value_label_arrow_width="thick",
    )

    style = Chart.from_dict(data).data_series[0].style

    assert style.value_label_arrow_style is ValueLabelArrowStyle.LINE
    assert style.value_label_arrow_line_style is ValueLabelArrowLineStyle.SOLID
    assert style.value_label_arrow_color == "#000000"
    assert style.value_label_arrow_width == 1.0


@pytest.mark.parametrize(("source", "target"), [("line", SeriesType.SCATTER), ("scatter", SeriesType.LINE)])
def test_retyping_between_line_and_scatter_keeps_the_arrow_styling(source, target):
    chart = _chart(source)
    for name, value in STYLED.items():
        setattr(chart.data_series[0].style, name, value)

    chart.retype_series(0, target)

    style = chart.data_series[0].style
    for name, value in STYLED.items():
        assert getattr(style, name) == value, name
