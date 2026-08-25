"""Regression test for mixing series types on one chart.

A chart's `allowed_series_types` (see `ChartTypeSpec`) restricts which
`SeriesType`s may coexist on it, rather than forcing every series to
share the chart's own type -- e.g. a VECTOR chart also allows LINE and
SCATTER series alongside vector arrows. Previously verified only by a
throwaway manual script; this test makes that verification permanent.
"""
from pandaplot.gui.components.tabs.chart.series_renderers import (
    SERIES_RENDERERS,
    render_line_series,
    render_vector_series,
)
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.chart.series_style import LineSeriesStyle, VectorSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart


def _mixed_chart() -> Chart:
    chart = Chart(name="Mixed", chart_type="vector")
    vector_series = chart.add_data_series(
        dataset_id="ds1", x_column_id="x", y_column_id="y",
        label="Field", series_type=SeriesType.VECTOR,
        style=VectorSeriesStyle(vector_color="#ff0000", u_column_id="u", v_column_id="v"),
    )
    line_series = chart.add_data_series(
        dataset_id="ds1", x_column_id="x", y_column_id="y",
        label="Trace", series_type=SeriesType.LINE,
        style=LineSeriesStyle(color="#00ff00", line_width=3.0),
    )
    return chart, vector_series, line_series


class TestMixedSeriesTypesOnOneChart:
    def test_vector_chart_type_allows_both_vector_and_line_series(self):
        """LINE/SCATTER/VECTOR now all mutually allow each other
        (CHART_TYPE_SPECS was broadened), so VECTOR's allowed set also
        includes SCATTER. This test still demonstrates the specific
        vector+line coexistence the class is about; the full three-member
        set is asserted exactly so the stale narrower matrix can't creep
        back in unnoticed."""
        allowed = CHART_TYPE_SPECS[ChartType.VECTOR].allowed_series_types

        assert {SeriesType.VECTOR, SeriesType.LINE} <= allowed
        assert allowed == {SeriesType.VECTOR, SeriesType.LINE, SeriesType.SCATTER}

    def test_chart_holds_one_vector_and_one_line_series_with_distinct_styles(self):
        chart, vector_series, line_series = _mixed_chart()

        assert len(chart.data_series) == 2
        assert vector_series.series_type == SeriesType.VECTOR
        assert line_series.series_type == SeriesType.LINE
        assert isinstance(vector_series.style, VectorSeriesStyle)
        assert isinstance(line_series.style, LineSeriesStyle)
        assert vector_series.style.vector_color == "#ff0000"
        assert line_series.style.color == "#00ff00"

    def test_each_series_dispatches_to_its_own_renderer(self):
        chart, vector_series, line_series = _mixed_chart()

        assert SERIES_RENDERERS[vector_series.series_type] is render_vector_series
        assert SERIES_RENDERERS[line_series.series_type] is render_line_series

    def test_round_trips_both_series_with_correct_types_and_styles(self):
        chart, _vector_series, _line_series = _mixed_chart()

        data = chart.to_dict()
        restored = Chart.from_dict(data)

        assert len(restored.data_series) == 2
        restored_vector, restored_line = restored.data_series

        assert restored_vector.series_type == SeriesType.VECTOR
        assert isinstance(restored_vector.style, VectorSeriesStyle)
        assert restored_vector.style.vector_color == "#ff0000"
        assert restored_vector.style.u_column_id == "u"
        assert restored_vector.style.v_column_id == "v"

        assert restored_line.series_type == SeriesType.LINE
        assert isinstance(restored_line.style, LineSeriesStyle)
        assert restored_line.style.color == "#00ff00"
        assert restored_line.style.line_width == 3.0

    def test_mutating_one_series_style_does_not_affect_the_other(self):
        chart, vector_series, line_series = _mixed_chart()

        vector_series.style.vector_color = "#123456"

        assert line_series.style.color == "#00ff00"
        assert vector_series.style is not line_series.style
