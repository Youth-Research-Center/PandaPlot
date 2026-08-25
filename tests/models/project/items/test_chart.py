"""Tests for the Chart model (pandaplot.models.project.items.chart.Chart)."""

import numpy as np
import pytest

from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style import (
    BarSeriesStyle,
    ColormapSeriesStyle,
    HeatmapSeriesStyle,
    HistSeriesStyle,
    LineSeriesStyle,
    ScatterSeriesStyle,
    VectorSeriesStyle,
)
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import (
    Chart,
    DataSeries,
    FitData,
    assign_series_column_ids,
    restore_chart_state,
    snapshot_chart_state,
)


class TestFitDataStyle:
    """FitData.style is authoritative, auto-derived like DataSeries.style."""

    def test_style_auto_derives_to_a_default_fitstyle(self):
        fit = FitData(source_dataset_id="ds1", fit_type="linear",
                       x_data=np.array([1.0]), y_data=np.array([2.0]), label="Fit")

        assert isinstance(fit.style, FitStyle)
        assert fit.style.color == "#ff7f0e"
        assert fit.style.band_fill_enabled is True

    def test_style_is_respected_when_passed_explicitly(self):
        fit = FitData(source_dataset_id="ds1", fit_type="linear",
                       x_data=np.array([1.0]), y_data=np.array([2.0]), label="Fit",
                       style=FitStyle(color="#112233", band_fill_enabled=False))

        assert fit.style.color == "#112233"
        assert fit.style.band_fill_enabled is False

    def test_flat_style_fields_no_longer_exist(self):
        fit = FitData(source_dataset_id="ds1", fit_type="linear",
                       x_data=np.array([1.0]), y_data=np.array([2.0]), label="Fit")

        assert not hasattr(fit, "color")
        assert not hasattr(fit, "line_style")
        assert not hasattr(fit, "line_width")
        assert not hasattr(fit, "alpha")


class TestFitDataConfidenceBandRoundTrip:
    """Regression test: Chart.to_dict()/from_dict() must not silently drop
    a fit's confidence_lower/confidence_upper arrays. Neither field was
    ever serialized -- saving and reopening any chart with a confidence
    band configured (Phase 5's headline feature) made the band disappear
    on reload, since FitData.confidence_lower/upper default to None."""

    def test_confidence_bands_survive_to_dict_from_dict(self):
        chart = Chart(name="C", chart_type="line")
        chart.add_fit_data(
            source_dataset_id="ds1", fit_type="linear",
            x_data=np.array([1.0, 2.0, 3.0]), y_data=np.array([1.0, 2.0, 3.0]),
            label="Fit",
            confidence_lower=np.array([0.5, 1.5, 2.5]),
            confidence_upper=np.array([1.5, 2.5, 3.5]),
        )

        restored = Chart.from_dict(chart.to_dict())

        fit = restored.fit_data[0]
        assert fit.confidence_lower is not None
        assert fit.confidence_upper is not None
        assert list(fit.confidence_lower) == [0.5, 1.5, 2.5]
        assert list(fit.confidence_upper) == [1.5, 2.5, 3.5]
        assert isinstance(fit.confidence_lower, np.ndarray)
        assert isinstance(fit.confidence_upper, np.ndarray)

    def test_absent_confidence_bands_round_trip_as_none(self):
        """A fit with no computed confidence band (the common case) must
        round-trip to None, not to a stray empty array or a crash."""
        chart = Chart(name="C", chart_type="line")
        chart.add_fit_data(
            source_dataset_id="ds1", fit_type="linear",
            x_data=np.array([1.0, 2.0]), y_data=np.array([1.0, 2.0]),
            label="Fit",
        )

        restored = Chart.from_dict(chart.to_dict())

        fit = restored.fit_data[0]
        assert fit.confidence_lower is None
        assert fit.confidence_upper is None


class TestChartTypeIsChartTypeEnum:
    """Chart.chart_type is a ChartType(str, Enum), not a plain str -- but
    every existing string-literal comparison in the codebase keeps
    working, since ChartType subclasses str (same pattern as
    DataSeries.y_axis/YAxis)."""

    def test_constructor_coerces_string_to_charttype(self):
        chart = Chart(name="C", chart_type="scatter")

        assert chart.chart_type == ChartType.SCATTER
        assert isinstance(chart.chart_type, ChartType)

    def test_constructor_accepts_a_charttype_instance_directly(self):
        chart = Chart(name="C", chart_type=ChartType.VECTOR)

        assert chart.chart_type == ChartType.VECTOR

    def test_constructor_defaults_to_line(self):
        chart = Chart(name="C")

        assert chart.chart_type == ChartType.LINE

    def test_set_chart_type_coerces_string(self):
        chart = Chart(name="C", chart_type="line")

        chart.set_chart_type("bar")

        assert chart.chart_type == ChartType.BAR

    def test_string_equality_still_works(self):
        # Existing call sites throughout chart_editor.py/resolve_series_data
        # compare chart.chart_type directly to string literals -- this must
        # keep working unchanged.
        chart = Chart(name="C", chart_type="hist")

        assert chart.chart_type == "hist"
        assert chart.chart_type != "line"

    def test_to_dict_serializes_as_plain_string(self):
        chart = Chart(name="C", chart_type="vector")

        data = chart.to_dict()

        assert data["chart_type"] == "vector"
        assert isinstance(data["chart_type"], str)

    def test_from_dict_round_trips_chart_type(self):
        chart = Chart(name="C", chart_type="scatter")
        data = chart.to_dict()

        restored = Chart.from_dict(data)

        assert restored.chart_type == ChartType.SCATTER

    def test_from_dict_defaults_missing_chart_type_to_line(self):
        restored = Chart.from_dict({"name": "C"})

        assert restored.chart_type == ChartType.LINE


class TestDataSeriesTypeAndStyle:
    """series_type/style are new, optional, additive fields -- every
    existing DataSeries(...) construction site (none of which pass these
    two new kwargs) keeps working via their defaults."""

    def test_defaults_when_not_specified(self):
        series = DataSeries(dataset_id="ds1", x_column="x", y_column="y")

        assert series.series_type == SeriesType.LINE
        assert isinstance(series.style, LineSeriesStyle)

    def test_accepts_a_seriestype_instance(self):
        series = DataSeries(dataset_id="ds1", x_column="x", y_column="y", series_type=SeriesType.VECTOR)

        assert series.series_type == SeriesType.VECTOR

    def test_coerces_a_string_series_type(self):
        series = DataSeries(dataset_id="ds1", x_column="x", y_column="y", series_type="scatter")

        assert series.series_type == SeriesType.SCATTER

    def test_accepts_an_explicit_style_object(self):
        style = VectorSeriesStyle(vector_color="#ff0000")
        series = DataSeries(dataset_id="ds1", x_column="x", y_column="y",
                             series_type=SeriesType.VECTOR, style=style)

        assert series.style is style
        assert series.style.vector_color == "#ff0000"


class TestChartSeriesTypeAndStyleRoundTrip:
    """A save-then-load cycle must reproduce series_type/style exactly --
    otherwise a migrated project's new fields would be silently dropped on
    the very next save."""

    def test_round_trips_series_type_and_style(self):
        chart = Chart(name="C", chart_type="line")
        style = LineSeriesStyle(color="#abcdef", line_width=3.5)
        chart.data_series.append(DataSeries(
            dataset_id="ds1", x_column="x", y_column="y",
            series_type=SeriesType.LINE, style=style,
        ))

        data = chart.to_dict()
        restored = Chart.from_dict(data)

        restored_series = restored.data_series[0]
        assert restored_series.series_type == SeriesType.LINE
        assert isinstance(restored_series.style, LineSeriesStyle)
        assert restored_series.style.color == "#abcdef"
        assert restored_series.style.line_width == 3.5

    def test_round_trips_a_series_constructed_with_no_explicit_style(self):
        # __post_init__ now auto-derives .style at construction time, so
        # this series already has a style before to_dict() ever runs --
        # round-tripping it must preserve that derived style, not lose it.
        chart = Chart(name="C", chart_type="line")
        chart.data_series.append(DataSeries(dataset_id="ds1", x_column="x", y_column="y"))

        data = chart.to_dict()
        restored = Chart.from_dict(data)

        assert isinstance(restored.data_series[0].style, LineSeriesStyle)

    def test_heatmap_series_round_trips_through_to_dict_from_dict(self):
        chart = Chart(name="C", chart_type="heatmap")
        chart.data_series.append(DataSeries(
            dataset_id="ds1", x_column_id="x-id", y_column_id="y-id",
            series_type=SeriesType.HEATMAP,
            style=HeatmapSeriesStyle(
                z_column_id="z-id",
                heatmap_gridding="binned", heatmap_resolution=64,
            ),
        ))

        data = chart.to_dict()
        restored = Chart.from_dict(data)

        restored_series = restored.data_series[0]
        restored_style = restored_series.style
        assert restored_series.series_type == SeriesType.HEATMAP
        assert isinstance(restored_style, HeatmapSeriesStyle)
        assert restored_style.z_column_id == "z-id"
        assert restored_style.heatmap_gridding == "binned"
        assert restored_style.heatmap_resolution == 64

    def test_colormap_series_round_trips_through_to_dict_from_dict(self):
        chart = Chart(name="C", chart_type="colormap")
        chart.data_series.append(DataSeries(
            dataset_id="ds1", x_column_id="x-id", y_column_id="y-id",
            series_type=SeriesType.COLORMAP,
            style=ColormapSeriesStyle(z_column_id="z-id"),
        ))

        data = chart.to_dict()
        restored = Chart.from_dict(data)

        restored_series = restored.data_series[0]
        restored_style = restored_series.style
        assert restored_series.series_type == SeriesType.COLORMAP
        assert isinstance(restored_style, ColormapSeriesStyle)
        assert restored_style.z_column_id == "z-id"

    def test_from_dict_defaults_series_type_to_chart_type_when_absent(self):
        # Simulates a legacy project not yet through
        # migrate_chart_legacy_to_v1 -- from_dict must still produce a
        # usable series_type.
        chart = Chart(name="C", chart_type="vector")
        raw = chart.to_dict()
        raw["data_series"] = [{
            "dataset_id": "ds1", "x_column": "x", "y_column": "y",
            # no "series_type" key at all.
        }]

        restored = Chart.from_dict(raw)

        assert restored.data_series[0].series_type == SeriesType.VECTOR


class TestSnapshotRestorePreservesStyleType:
    """snapshot_chart_state/restore_chart_state back the properties-panel
    cancel/undo flow. dataclasses.asdict(series) recursively flattens
    nested dataclasses to plain dicts -- DataSeries(**d) then constructs a
    DataSeries whose .style field holds that plain dict, not a
    reconstructed SeriesStyleBase instance, unless restore explicitly
    rebuilds it via style_cls."""

    def test_restore_reconstructs_style_as_a_dataclass_not_a_dict(self):
        chart = Chart(name="C", chart_type="line")
        style = LineSeriesStyle(color="#123456")
        chart.data_series.append(DataSeries(
            dataset_id="ds1", x_column="x", y_column="y",
            series_type=SeriesType.LINE, style=style,
        ))

        snapshot = snapshot_chart_state(chart)
        chart.data_series[0].style = LineSeriesStyle(color="#ffffff")  # simulate an in-progress edit
        restore_chart_state(chart, snapshot)

        restored_style = chart.data_series[0].style
        assert isinstance(restored_style, LineSeriesStyle)
        assert restored_style.color == "#123456"

    def test_restore_handles_a_series_constructed_with_no_explicit_style(self):
        # __post_init__ now auto-derives .style at construction time, so
        # this series already has a style before the snapshot is taken --
        # restore must preserve that derived style, not lose it.
        chart = Chart(name="C", chart_type="line")
        chart.data_series.append(DataSeries(dataset_id="ds1", x_column="x", y_column="y"))

        snapshot = snapshot_chart_state(chart)
        restore_chart_state(chart, snapshot)

        assert isinstance(chart.data_series[0].style, LineSeriesStyle)


class TestDataSeriesAutoDerivesStyle:
    """.style is auto-populated in __post_init__ whenever not explicitly
    given -- closing the gap Phase 3a's final review flagged (nothing
    populated .style for a series created after Phase 3a shipped).

    Since Phase 3c Task 4 deleted the flat styling fields (and the
    `derive_style` bridge that read them), a fresh series with no explicit
    `style=` now gets its style class's own defaults rather than anything
    derived from flat kwargs -- there are no flat kwargs left to derive
    from."""

    def test_fresh_line_series_gets_default_line_style(self):
        series = DataSeries(dataset_id="ds1", x_column="x", y_column="y",
                             series_type=SeriesType.LINE)

        assert isinstance(series.style, LineSeriesStyle)
        assert series.style == LineSeriesStyle()

    def test_fresh_vector_series_gets_default_vector_style(self):
        series = DataSeries(dataset_id="ds1", x_column="x", y_column="y",
                             series_type=SeriesType.VECTOR)

        assert isinstance(series.style, VectorSeriesStyle)
        assert series.style == VectorSeriesStyle()

    def test_explicit_style_is_not_overwritten(self):
        explicit = LineSeriesStyle(color="#explicit")
        series = DataSeries(dataset_id="ds1", x_column="x", y_column="y",
                             series_type=SeriesType.LINE, style=explicit)

        assert series.style is explicit


class TestDataSeriesRejectsMismatchedStyle:
    """DataSeries must reject a style whose concrete class doesn't match
    series_type's own registered style_cls -- a mismatched pair isn't
    just cosmetically wrong: the renderer dispatches on series_type and
    will read fields the wrong style class doesn't declare, and a
    save/reload round-trip is guaranteed to fail (from_dict rebuilds the
    class series_type says it should be, from fields belonging to a
    different one)."""

    def test_vector_style_on_a_line_series_raises(self):
        with pytest.raises(ValueError, match="LineSeriesStyle"):
            DataSeries(dataset_id="ds1", series_type=SeriesType.LINE,
                       style=VectorSeriesStyle())

    def test_line_style_on_a_scatter_series_raises(self):
        with pytest.raises(ValueError, match="ScatterSeriesStyle"):
            DataSeries(dataset_id="ds1", series_type=SeriesType.SCATTER,
                       style=LineSeriesStyle())

    def test_matching_style_is_accepted(self):
        series = DataSeries(dataset_id="ds1", series_type=SeriesType.BAR,
                             style=BarSeriesStyle(color="#112233"))

        assert series.style.color == "#112233"


class TestSetChartTypeRetypesSeries:
    """set_chart_type must retype only series whose current type is NOT
    allowed under the new chart type -- otherwise chart_editor.py's
    renderer picks its dispatch function from the chart's new type but
    still finds series whose .style is the OLD style class, and crashes
    trying to read fields the wrong class doesn't declare (the
    derive_style-removal regression fixed in Phase 3c). Series whose type
    IS allowed under the new chart type (e.g. a LINE series when the
    chart becomes "vector", since Vector's spec allows {VECTOR, LINE})
    must be left completely untouched, since mixed series types are
    legitimate under that combination."""

    def test_disallowed_series_type_gets_retyped_to_the_new_chart_defaults(self):
        chart = Chart(name="C", chart_type="line")
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               style=LineSeriesStyle(color="#112233"))

        chart.set_chart_type("hist")

        series = chart.data_series[0]
        assert series.series_type == SeriesType.HIST
        assert isinstance(series.style, HistSeriesStyle)
        assert series.style.color == "#112233"

    def test_vector_to_line_stays_vector_since_now_allowed(self):
        chart = Chart(name="C", chart_type="vector")
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               style=VectorSeriesStyle(vector_color="#445566"))
        original_style = chart.data_series[0].style

        chart.set_chart_type("line")

        series = chart.data_series[0]
        assert series.series_type == SeriesType.VECTOR
        assert series.style is original_style

    def test_line_series_stays_line_when_chart_becomes_vector_since_line_is_allowed(self):
        chart = Chart(name="C", chart_type="line")
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               style=LineSeriesStyle(color="#112233"))
        original_style = chart.data_series[0].style

        chart.set_chart_type("vector")

        series = chart.data_series[0]
        assert series.series_type == SeriesType.LINE
        assert series.style is original_style

    def test_scatter_series_stays_scatter_across_line_and_bar_since_both_allow_it(self):
        chart = Chart(name="C", chart_type="line")
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               series_type=SeriesType.SCATTER)
        original_style = chart.data_series[0].style

        chart.set_chart_type("bar")

        series = chart.data_series[0]
        assert series.series_type == SeriesType.SCATTER
        assert series.style is original_style

    def test_setting_the_same_type_is_a_no_op(self):
        chart = Chart(name="C", chart_type="line")
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               style=LineSeriesStyle(color="#112233"))
        original_style = chart.data_series[0].style

        chart.set_chart_type("line")

        assert chart.data_series[0].style is original_style

    def test_multi_series_chart_each_keeps_its_own_color(self):
        chart = Chart(name="C", chart_type="line")
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               style=LineSeriesStyle(color="#111111"))
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               style=LineSeriesStyle(color="#222222"))

        chart.set_chart_type("bar")

        assert chart.data_series[0].series_type == SeriesType.BAR
        assert isinstance(chart.data_series[0].style, BarSeriesStyle)
        assert chart.data_series[0].style.color == "#111111"
        assert chart.data_series[1].series_type == SeriesType.BAR
        assert isinstance(chart.data_series[1].style, BarSeriesStyle)
        assert chart.data_series[1].style.color == "#222222"

    def test_mixed_chart_only_retypes_the_disallowed_series(self):
        """A chart with one LINE and one HIST series switching to "vector"
        (allowed_series_types = {VECTOR, LINE}): the LINE series stays
        untouched, the HIST series (not allowed) gets retyped to VECTOR."""
        chart = Chart(name="C", chart_type="line")
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               style=LineSeriesStyle(color="#111111"))
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               series_type=SeriesType.HIST,
                               style=HistSeriesStyle(color="#222222"))
        line_style = chart.data_series[0].style

        chart.set_chart_type("vector")

        assert chart.data_series[0].series_type == SeriesType.LINE
        assert chart.data_series[0].style is line_style

        retyped = chart.data_series[1]
        assert retyped.series_type == SeriesType.VECTOR
        assert isinstance(retyped.style, VectorSeriesStyle)
        assert retyped.style.vector_color == "#222222"


class TestRetypeSeries:
    """Chart.retype_series retypes a single series explicitly -- the same
    per-series logic set_chart_type applies in bulk when a chart-type
    change makes a series' type disallowed, but callable directly for an
    explicit per-series type change (Phase 4c's Series Type selector)."""

    def test_retypes_a_single_series_and_carries_color(self):
        chart = Chart(name="C", chart_type="line")
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               style=LineSeriesStyle(color="#112233"))

        chart.retype_series(0, "hist")

        series = chart.data_series[0]
        assert series.series_type == SeriesType.HIST
        assert isinstance(series.style, HistSeriesStyle)
        assert series.style.color == "#112233"

    def test_retyping_to_vector_carries_color_into_vector_color(self):
        chart = Chart(name="C", chart_type="line")
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               style=LineSeriesStyle(color="#445566"))

        chart.retype_series(0, "vector")

        series = chart.data_series[0]
        assert series.series_type == SeriesType.VECTOR
        assert isinstance(series.style, VectorSeriesStyle)
        assert series.style.vector_color == "#445566"

    def test_retyping_to_the_same_type_is_a_no_op(self):
        chart = Chart(name="C", chart_type="line")
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               style=LineSeriesStyle(color="#112233"))
        original_style = chart.data_series[0].style

        chart.retype_series(0, "line")

        assert chart.data_series[0].style is original_style

    def test_only_the_targeted_series_is_retyped(self):
        chart = Chart(name="C", chart_type="line")
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               style=LineSeriesStyle(color="#111111"))
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                               style=LineSeriesStyle(color="#222222"))
        untouched_style = chart.data_series[1].style

        chart.retype_series(0, "scatter")

        assert chart.data_series[0].series_type == SeriesType.SCATTER
        assert chart.data_series[1].series_type == SeriesType.LINE
        assert chart.data_series[1].style is untouched_style

    def test_retyping_line_to_scatter_carries_over_error_bars_and_marker(self):
        """Regression test: a Line series' already-configured error bars
        and marker styling must survive a retype to Scatter (both style
        classes compose marker/error_bars) -- reported live as "if I move
        from line chart with error bars to scatter, I lose error bars,"
        caused by retype_series only ever carrying the base color into a
        brand-new style object and discarding everything else."""
        chart = Chart(name="C", chart_type="line")
        chart.add_data_series(
            dataset_id="ds1", x_column_id="x", y_column_id="y",
            style=LineSeriesStyle(
                color="#112233",
                marker=MarkerStyle(marker_color="#445566", marker_size=5.0),
                error_bars=ErrorBarConfig(y_error_column_id="err-col", error_cap_size=7.0),
            ),
        )

        chart.retype_series(0, "scatter")

        series = chart.data_series[0]
        assert series.series_type == SeriesType.SCATTER
        assert isinstance(series.style, ScatterSeriesStyle)
        assert series.style.color == "#112233"
        assert series.style.marker.marker_color == "#445566"
        assert series.style.marker.marker_size == 5.0
        assert series.style.error_bars.y_error_column_id == "err-col"
        assert series.style.error_bars.error_cap_size == 7.0

    def test_retyping_line_to_scatter_does_not_alias_the_carried_error_bars(self):
        """The carried-over error_bars/marker must be independent copies,
        not shared references with the old (now-discarded) style object --
        otherwise a later edit to the new series' error bars would reach
        back and mutate an object nothing else should still hold."""
        chart = Chart(name="C", chart_type="line")
        old_style = LineSeriesStyle(error_bars=ErrorBarConfig(y_error_column_id="err-col"))
        chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y", style=old_style)

        chart.retype_series(0, "scatter")

        chart.data_series[0].style.error_bars.y_error_column_id = "changed"
        assert old_style.error_bars.y_error_column_id == "err-col"

    def test_retyping_line_to_hist_drops_error_bars_since_hist_has_none(self):
        """Hist has no error_bars field at all -- retyping into it must not
        try to carry anything over (and must not crash)."""
        chart = Chart(name="C", chart_type="line")
        chart.add_data_series(
            dataset_id="ds1", x_column_id="x", y_column_id="y",
            style=LineSeriesStyle(error_bars=ErrorBarConfig(y_error_column_id="err-col")),
        )

        chart.retype_series(0, "hist")

        series = chart.data_series[0]
        assert isinstance(series.style, HistSeriesStyle)
        assert not hasattr(series.style, "error_bars")


class TestChartAddDataSeriesDefaultsSeriesType:
    """add_data_series defaults series_type from the chart's own type when
    the caller doesn't pass one -- without this, every series added via
    the Data tab or the wizard would default to SeriesType.LINE regardless
    of the chart's real type (the exact gap Phase 3a's review flagged)."""

    def test_defaults_series_type_from_chart_type(self):
        chart = Chart(name="C", chart_type="bar")

        series = chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y")

        assert series.series_type == SeriesType.BAR
        assert isinstance(series.style, BarSeriesStyle)

    def test_explicit_series_type_kwarg_is_respected(self):
        chart = Chart(name="C", chart_type="line")

        series = chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                                        series_type=SeriesType.SCATTER)

        assert series.series_type == SeriesType.SCATTER

    def test_vector_chart_add_series_gets_vector_style_with_passed_color(self):
        chart = Chart(name="C", chart_type="vector")

        series = chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                                        style=VectorSeriesStyle(vector_color="#abcdef"))

        assert series.series_type == SeriesType.VECTOR
        assert isinstance(series.style, VectorSeriesStyle)
        assert series.style.vector_color == "#abcdef"


class _FakeDataset:
    """Minimal dataset stand-in for assign_series_column_ids tests --
    mirrors the pattern in tests/models/test_data_series_vector_fields.py."""

    def __init__(self, mapping):
        self._mapping = mapping

    def column_id(self, name):
        return self._mapping.get(name)


class TestAssignSeriesColumnIdsBackfillsZColumn:
    """assign_series_column_ids must backfill style.z_column_id from
    style.z_column for ColormapSeriesStyle/HeatmapSeriesStyle, mirroring
    the existing VectorSeriesStyle u/v/magnitude branch -- otherwise a
    legacy-format chart (name-only, no ids) loaded for a Colormap/Heatmap
    series would never get its Z column resolved to a stable id."""

    def test_backfills_z_column_id_for_heatmap_style(self):
        series = DataSeries(
            dataset_id="ds1", series_type=SeriesType.HEATMAP,
            style=HeatmapSeriesStyle(z_column="z_name"),
        )
        assign_series_column_ids(series, _FakeDataset({"z_name": "z-id"}))
        assert series.style.z_column_id == "z-id"

    def test_backfills_z_column_id_for_colormap_style(self):
        series = DataSeries(
            dataset_id="ds1", series_type=SeriesType.COLORMAP,
            style=ColormapSeriesStyle(z_column="z_name"),
        )
        assign_series_column_ids(series, _FakeDataset({"z_name": "z-id"}))
        assert series.style.z_column_id == "z-id"

    def test_does_not_overwrite_an_already_set_z_column_id(self):
        """Guard must match the Vector branch's exact pattern: only
        backfill when z_column_id is currently empty."""
        series = DataSeries(
            dataset_id="ds1", series_type=SeriesType.HEATMAP,
            style=HeatmapSeriesStyle(z_column="z_name", z_column_id="existing-id"),
        )
        assign_series_column_ids(series, _FakeDataset({"z_name": "z-id"}))
        assert series.style.z_column_id == "existing-id"

    def test_leaves_z_column_id_empty_when_z_column_unset(self):
        series = DataSeries(
            dataset_id="ds1", series_type=SeriesType.HEATMAP,
            style=HeatmapSeriesStyle(),
        )
        assign_series_column_ids(series, _FakeDataset({}))
        assert series.style.z_column_id == ""


class TestChartConfigHasColorMapDefaults:
    """Chart.config gains 6 color map keys with sensible defaults. These keys
    are shared across every Colormap/Heatmap series on a chart (since there is
    only ever one physical colorbar drawn) and live on Chart.config rather than
    per-series style objects -- the per-series colormap/colorbar_show/etc.
    fields that used to live on ColormapSeriesStyle/HeatmapSeriesStyle were
    removed in favor of these shared chart-level values."""

    def test_chart_config_has_color_map_defaults(self):
        chart = Chart(name="C", chart_type="line")
        assert chart.config["colormap"] == "viridis"
        assert chart.config["colorbar_show"] is True
        assert chart.config["colorbar_label"] == ""
        assert chart.config["color_scale_auto"] is True
        assert chart.config["color_vmin"] == 0.0
        assert chart.config["color_vmax"] == 1.0

    def test_chart_config_color_map_fields_round_trip_through_to_dict_from_dict(self):
        chart = Chart(name="C", chart_type="heatmap")
        chart.config["colormap"] = "plasma"
        chart.config["colorbar_show"] = False
        chart.config["colorbar_label"] = "Temp (C)"
        chart.config["color_scale_auto"] = False
        chart.config["color_vmin"] = -5.0
        chart.config["color_vmax"] = 42.0

        data = chart.to_dict()
        restored = Chart.from_dict(data)

        assert restored.config["colormap"] == "plasma"
        assert restored.config["colorbar_show"] is False
        assert restored.config["colorbar_label"] == "Temp (C)"
        assert restored.config["color_scale_auto"] is False
        assert restored.config["color_vmin"] == -5.0
        assert restored.config["color_vmax"] == 42.0


class TestRetypeSeriesToColormapCarriesOverMarker:
    """ColormapSeriesStyle.marker is a MarkerStyle field like Line/Scatter's
    -- retype_series' existing generic
    `hasattr(old_style, "marker") and hasattr(new_style, "marker")` carry-over
    logic should pick it up with no dedicated Colormap/Heatmap code needed.
    Verified directly here rather than just trusting that claim."""

    def test_retyping_scatter_to_colormap_carries_over_marker(self):
        chart = Chart(name="C", chart_type="scatter")
        chart.add_data_series(
            dataset_id="ds1", x_column_id="x", y_column_id="y",
            style=ScatterSeriesStyle(marker=MarkerStyle(marker_size=9.0, marker_color="#445566")),
        )

        chart.retype_series(0, "colormap")

        series = chart.data_series[0]
        assert series.series_type == SeriesType.COLORMAP
        assert isinstance(series.style, ColormapSeriesStyle)
        assert series.style.marker.marker_size == 9.0
        assert series.style.marker.marker_color == "#445566"

    def test_retyping_colormap_to_scatter_carries_marker_back(self):
        chart = Chart(name="C", chart_type="colormap")
        chart.add_data_series(
            dataset_id="ds1", x_column_id="x", y_column_id="y",
            style=ColormapSeriesStyle(marker=MarkerStyle(marker_size=12.0)),
        )

        chart.retype_series(0, "scatter")

        series = chart.data_series[0]
        assert series.series_type == SeriesType.SCATTER
        assert isinstance(series.style, ScatterSeriesStyle)
        assert series.style.marker.marker_size == 12.0

    def test_retyping_scatter_to_heatmap_does_not_crash_since_heatmap_has_no_marker(self):
        """HeatmapSeriesStyle has no marker field at all (marker_mode is
        "unsupported") -- retyping into it must not try to carry one over,
        and must not crash."""
        chart = Chart(name="C", chart_type="scatter")
        chart.add_data_series(
            dataset_id="ds1", x_column_id="x", y_column_id="y",
            style=ScatterSeriesStyle(marker=MarkerStyle(marker_size=9.0)),
        )

        chart.retype_series(0, "heatmap")

        series = chart.data_series[0]
        assert series.series_type == SeriesType.HEATMAP
        assert isinstance(series.style, HeatmapSeriesStyle)
        assert not hasattr(series.style, "marker")

    def test_retyping_heatmap_to_colormap_carries_over_z_column(self):
        """Heatmap and Colormap both require a Z column -- retyping between
        them must not force the user to re-pick the same column. Pins a
        regression where retype_series built a fresh style() and dropped
        z_column_id/z_column entirely, silently unresolving the series."""
        chart = Chart(name="C", chart_type="heatmap")
        chart.add_data_series(
            dataset_id="ds1", x_column_id="x", y_column_id="y",
            style=HeatmapSeriesStyle(z_column_id="z-id", z_column="z"),
        )

        chart.retype_series(0, "colormap")

        series = chart.data_series[0]
        assert series.series_type == SeriesType.COLORMAP
        assert isinstance(series.style, ColormapSeriesStyle)
        assert series.style.z_column_id == "z-id"
        assert series.style.z_column == "z"

    def test_retyping_colormap_to_heatmap_carries_over_z_column(self):
        chart = Chart(name="C", chart_type="colormap")
        chart.add_data_series(
            dataset_id="ds1", x_column_id="x", y_column_id="y",
            style=ColormapSeriesStyle(z_column_id="z-id", z_column="z"),
        )

        chart.retype_series(0, "heatmap")

        series = chart.data_series[0]
        assert series.series_type == SeriesType.HEATMAP
        assert isinstance(series.style, HeatmapSeriesStyle)
        assert series.style.z_column_id == "z-id"
        assert series.style.z_column == "z"
