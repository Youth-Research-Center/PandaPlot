"""Tests for CHART_TYPE_SPECS, absorbing chart_role_spec.py's
CHART_ROLE_SPECS content (display_name/roles/required_roles, unchanged
values) plus the new allowed_series_types/allows_fit/default_series_type
fields from the design's allowed-series-types-per-chart-type table.
supports_error_bars is a property, not a stored field -- reconciled with
SeriesTypeSpec rather than duplicated (see chart_type_spec.py's
docstring).
"""
import pytest

from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS, get_chart_type_spec
from pandaplot.models.chart.series_type import SeriesType


def test_every_chart_type_is_registered():
    """Asserted against the ChartType enum itself rather than a hardcoded
    list: the bug worth catching is a chart type that exists but has no
    spec (every consumer of CHART_TYPE_SPECS would KeyError on it), and
    that stays caught without this test needing an edit each time a type
    is added."""
    assert set(CHART_TYPE_SPECS.keys()) == set(ChartType)


def test_line_spec_matches_former_chart_role_spec_values():
    spec = CHART_TYPE_SPECS[ChartType.LINE]
    assert spec.display_name == "Line"
    assert spec.roles == ("x", "y")
    assert spec.required_roles == ("y",)
    assert spec.supports_error_bars is True


def test_hist_spec_matches_former_chart_role_spec_values():
    spec = CHART_TYPE_SPECS[ChartType.HIST]
    assert spec.display_name == "Histogram"
    assert spec.roles == ("values",)
    assert spec.required_roles == ("values",)
    assert spec.supports_error_bars is False


def test_vector_spec_matches_former_chart_role_spec_values():
    spec = CHART_TYPE_SPECS[ChartType.VECTOR]
    assert spec.display_name == "Vector"
    assert spec.roles == ("x", "y", "u", "v", "magnitude")
    assert spec.required_roles == ("x", "y", "u", "v")
    assert spec.supports_error_bars is False


def test_allowed_series_types_per_chart_type():
    lsv = {SeriesType.LINE, SeriesType.SCATTER, SeriesType.VECTOR}
    assert CHART_TYPE_SPECS[ChartType.LINE].allowed_series_types == lsv
    assert CHART_TYPE_SPECS[ChartType.SCATTER].allowed_series_types == lsv
    assert CHART_TYPE_SPECS[ChartType.VECTOR].allowed_series_types == lsv
    assert CHART_TYPE_SPECS[ChartType.BAR].allowed_series_types == {SeriesType.BAR, SeriesType.SCATTER}
    assert CHART_TYPE_SPECS[ChartType.HIST].allowed_series_types == {SeriesType.HIST}


def test_allowed_series_types_is_genuinely_immutable():
    """Regression test: ChartTypeSpec is @dataclass(frozen=True), but that
    alone only stops `spec.allowed_series_types = ...` (reassigning the
    field) -- a plain `set` value is still mutable in place. Since
    CHART_TYPE_SPECS is a shared, module-level registry, an in-place
    `.add()`/`.remove()` anywhere would silently corrupt every chart that
    consults this same spec object. allowed_series_types must be a real
    frozenset, not a set, to actually be immutable."""
    spec = CHART_TYPE_SPECS[ChartType.LINE]
    assert isinstance(spec.allowed_series_types, frozenset)
    with pytest.raises(AttributeError):
        spec.allowed_series_types.add(SeriesType.HIST)


def test_fits_are_allowed_on_every_2d_xy_chart_type_and_nothing_else():
    # COLORMAP/HEATMAP were the first types with allows_fit=False (a curve
    # fit doesn't apply to a Z-column colour series); every 3-D type joins
    # them, since a 2-D curve fit has no meaning on a 3-D chart.
    no_fit = {ChartType.COLORMAP, ChartType.HEATMAP} | {
        chart_type for chart_type, spec in CHART_TYPE_SPECS.items() if spec.is_3d
    }
    for chart_type, spec in CHART_TYPE_SPECS.items():
        assert spec.allows_fit == (chart_type not in no_fit)


def test_default_series_type_matches_chart_type():
    # Every chart type's default series type is itself, today -- since
    # DataSeries has no series_type field yet (Phase 3), a chart's type
    # IS its (only) series' type.
    for chart_type, spec in CHART_TYPE_SPECS.items():
        assert spec.default_series_type.value == chart_type.value


def test_supports_error_bars_is_computed_not_duplicated_from_series_type_spec():
    from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS

    for _chart_type, spec in CHART_TYPE_SPECS.items():
        assert spec.supports_error_bars == SERIES_TYPE_SPECS[spec.default_series_type].supports_error_bars


def test_get_chart_type_spec_accepts_a_plain_string():
    spec = get_chart_type_spec("hist")
    assert spec.display_name == "Histogram"


def test_get_chart_type_spec_accepts_a_charttype_instance():
    spec = get_chart_type_spec(ChartType.VECTOR)
    assert spec.display_name == "Vector"


def test_get_chart_type_spec_raises_on_unknown_type():
    with pytest.raises(ValueError):
        get_chart_type_spec("violin")


def test_compatible_chart_types_line_scatter_vector_are_mutually_compatible():
    from pandaplot.models.chart.chart_type_spec import compatible_chart_types
    lsv = {ChartType.LINE, ChartType.SCATTER, ChartType.VECTOR}
    assert compatible_chart_types(ChartType.LINE) & lsv == lsv
    assert compatible_chart_types(ChartType.SCATTER) & lsv == lsv
    assert compatible_chart_types(ChartType.VECTOR) & lsv == lsv


def test_compatible_chart_types_vector_to_bar_is_disabled():
    """Reported live: "I don't think we should support going from vector
    to barchart." VECTOR's default series type isn't in BAR's
    allowed_series_types, so it's excluded."""
    from pandaplot.models.chart.chart_type_spec import compatible_chart_types
    assert ChartType.BAR not in compatible_chart_types(ChartType.VECTOR)


def test_compatible_chart_types_scatter_to_bar_is_enabled():
    """Existing, preserved case: a Scatter chart's default series type
    (SCATTER) is allowed on Bar charts."""
    from pandaplot.models.chart.chart_type_spec import compatible_chart_types
    assert ChartType.BAR in compatible_chart_types(ChartType.SCATTER)


def test_compatible_chart_types_bar_to_scatter_is_disabled():
    """Asymmetric with the case above: Bar's default series type (BAR)
    isn't allowed on a Scatter chart, so switching away from Bar always
    force-retypes -- now visible as a disabled option instead of silent."""
    from pandaplot.models.chart.chart_type_spec import compatible_chart_types
    assert ChartType.SCATTER not in compatible_chart_types(ChartType.BAR)


def test_compatible_chart_types_hist_is_isolated_both_ways():
    from pandaplot.models.chart.chart_type_spec import compatible_chart_types
    assert compatible_chart_types(ChartType.HIST) == frozenset({ChartType.HIST})
    for chart_type in CHART_TYPE_SPECS:
        if chart_type != ChartType.HIST:
            assert ChartType.HIST not in compatible_chart_types(chart_type)


def test_compatible_chart_types_always_includes_self():
    from pandaplot.models.chart.chart_type_spec import compatible_chart_types
    for chart_type in CHART_TYPE_SPECS:
        assert chart_type in compatible_chart_types(chart_type)


def test_compatible_chart_types_for_series_empty_returns_all_chart_types():
    from pandaplot.models.chart.chart_type_spec import compatible_chart_types_for_series
    assert compatible_chart_types_for_series(frozenset()) == frozenset(CHART_TYPE_SPECS.keys())


def test_compatible_chart_types_for_series_single_scatter_matches_compatible_chart_types():
    """A chart whose only series is SCATTER should report the same
    compatible set as `compatible_chart_types(ChartType.SCATTER)` --
    SCATTER's own default_series_type IS scatter, so the two functions
    agree in this specific single-type case."""
    from pandaplot.models.chart.chart_type_spec import (
        compatible_chart_types,
        compatible_chart_types_for_series,
    )
    assert (
        compatible_chart_types_for_series({SeriesType.SCATTER})
        == compatible_chart_types(ChartType.SCATTER)
    )


def test_compatible_chart_types_for_series_mixed_scatter_and_vector_excludes_bar():
    """The exact reviewer scenario from PR #180: a Scatter chart holding
    both a SCATTER series and a VECTOR series must NOT report Bar as a
    safe switch target, even though `compatible_chart_types(SCATTER)`
    alone (which only looks at the chart's nominal type) WOULD include
    Bar. BAR's allowed_series_types is {BAR, SCATTER}, which doesn't
    include VECTOR, so switching would silently retype (and drop the
    configuration of) the VECTOR series."""
    from pandaplot.models.chart.chart_type_spec import (
        compatible_chart_types,
        compatible_chart_types_for_series,
    )
    mixed = {SeriesType.SCATTER, SeriesType.VECTOR}
    assert ChartType.BAR not in compatible_chart_types_for_series(mixed)
    assert ChartType.BAR in compatible_chart_types(ChartType.SCATTER)


def test_compatible_chart_types_for_series_single_vector_matches_existing_vector_behavior():
    from pandaplot.models.chart.chart_type_spec import compatible_chart_types_for_series
    result = compatible_chart_types_for_series({SeriesType.VECTOR})
    assert ChartType.BAR not in result
    assert ChartType.LINE in result
    assert ChartType.SCATTER in result
    assert ChartType.VECTOR in result
