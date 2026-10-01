"""Model-layer tests for the Stacked Bar chart/series type (#396).

Stacked Bar reuses BarSeriesStyle as-is, so its spec entries should match
Bar's everywhere except the stacking itself -- these tests pin that, plus
the Bar <-> Stacked Bar chart-type switch that sharing a style class makes
lossless.
"""
from dataclasses import fields

from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.chart_type_spec import (
    CHART_TYPE_SPECS,
    compatible_chart_types,
    compatible_chart_types_for_series,
)
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style import BarSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items.chart import Chart, DataSeries


def test_stacked_bar_series_spec_matches_bar_apart_from_stacking():
    bar = SERIES_TYPE_SPECS[SeriesType.BAR]
    stacked = SERIES_TYPE_SPECS[SeriesType.STACKED_BAR]

    assert stacked.style_cls is BarSeriesStyle
    assert stacked.is_stacked is True
    assert bar.is_stacked is False
    for spec_field in fields(stacked):
        if spec_field.name != "is_stacked":
            assert getattr(stacked, spec_field.name) == getattr(bar, spec_field.name), spec_field.name


def test_only_stacked_bar_is_stacked():
    for series_type in SeriesType:
        assert SERIES_TYPE_SPECS[series_type].is_stacked is (series_type == SeriesType.STACKED_BAR), series_type


def test_stacked_bar_chart_spec():
    spec = CHART_TYPE_SPECS[ChartType.STACKED_BAR]
    assert spec.display_name == "Stacked Bar"
    assert spec.roles == CHART_TYPE_SPECS[ChartType.BAR].roles == ("x", "y")
    assert spec.required_roles == ("y",)
    assert spec.supports_error_bars is True
    assert spec.is_3d is False
    assert spec.default_series_type == SeriesType.STACKED_BAR
    assert spec.allowed_series_types == {SeriesType.STACKED_BAR, SeriesType.SCATTER}


def test_bar_and_stacked_bar_charts_can_switch_into_each_other():
    """Neither allows the other's bar series type as-is, but the retype
    between them is lossless (one shared style class), so the switch must
    stay offered in both directions."""
    assert ChartType.STACKED_BAR in compatible_chart_types(ChartType.BAR)
    assert ChartType.BAR in compatible_chart_types(ChartType.STACKED_BAR)
    assert ChartType.STACKED_BAR in compatible_chart_types_for_series(frozenset({SeriesType.BAR, SeriesType.SCATTER}))
    assert ChartType.BAR in compatible_chart_types_for_series(frozenset({SeriesType.STACKED_BAR}))


def test_lossless_retype_rule_does_not_open_any_other_switch():
    """Only Bar/Stacked Bar share a style class, so no other pair of chart
    types became switchable."""
    for chart_type in CHART_TYPE_SPECS:
        if chart_type not in (ChartType.BAR, ChartType.STACKED_BAR, ChartType.SCATTER):
            assert ChartType.STACKED_BAR not in compatible_chart_types(chart_type), chart_type
    assert compatible_chart_types(ChartType.STACKED_BAR) == {ChartType.STACKED_BAR, ChartType.BAR}


def test_switching_a_bar_chart_to_stacked_bar_retypes_its_bars_and_keeps_their_style():
    chart = Chart(name="Bars", chart_type=ChartType.BAR)
    style = BarSeriesStyle(
        color="#123456", show_value_labels=True,
        value_label_text_color="#abcdef", value_label_bg_color="#fedcba", value_label_bg_alpha=0.4,
        error_bars=ErrorBarConfig(y_error_column_id="col-err", error_cap_size=6.0),
    )
    chart.data_series.append(DataSeries(dataset_id="ds", y_column_id="col-y", series_type=SeriesType.BAR, style=style))
    chart.data_series.append(DataSeries(dataset_id="ds", y_column_id="col-y", series_type=SeriesType.SCATTER))

    chart.set_chart_type(ChartType.STACKED_BAR)

    assert chart.data_series[0].series_type == SeriesType.STACKED_BAR
    assert chart.data_series[0].style == style
    # Scatter is allowed on both, so it's left alone.
    assert chart.data_series[1].series_type == SeriesType.SCATTER

    chart.set_chart_type(ChartType.BAR)

    assert chart.data_series[0].series_type == SeriesType.BAR
    assert chart.data_series[0].style == style


def test_stacked_bar_series_round_trips_through_serialization():
    chart = Chart(name="Stacked", chart_type=ChartType.STACKED_BAR)
    chart.data_series.append(DataSeries(
        dataset_id="ds", y_column_id="col-y", series_type=SeriesType.STACKED_BAR,
        style=BarSeriesStyle(color="#ff0000", show_value_labels=True),
    ))

    reloaded = Chart.from_dict(chart.to_dict())

    assert reloaded.chart_type == ChartType.STACKED_BAR
    assert reloaded.data_series[0].series_type == SeriesType.STACKED_BAR
    assert reloaded.data_series[0].style == BarSeriesStyle(color="#ff0000", show_value_labels=True)
