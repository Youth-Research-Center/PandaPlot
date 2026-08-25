"""Tests for the per-item chart migration dispatcher.

As of this refactor, PER_ITEM_CHART_MIGRATIONS has a single real entry
(migrate_chart_legacy_to_v1, see TestMigrateChartLegacyToV1 below) --
formerly two steps (migrate_chart_v1_to_v2 for series, migrate_chart_v2_to_v3
for fits), collapsed into one since neither had ever shipped to a real user
and there was no intermediate shape worth preserving. The dispatcher-loop
tests below patch the registry to whatever shape each scenario needs --
pinning down migrate_chart's loop behavior in isolation from the real
migration content, the same way test_runner.py does for the cross-item
runner.
"""
from unittest.mock import patch

from pandaplot.models.migrations.per_item.chart import migrate_chart, migrate_chart_legacy_to_v1


def test_noop_when_registry_is_empty():
    raw = {"chart_type": "line"}

    with patch(
        "pandaplot.models.migrations.per_item.chart.PER_ITEM_CHART_MIGRATIONS", {}
    ), patch("pandaplot.models.migrations.per_item.chart.CURRENT_SCHEMA_VERSION", 2):
        # schema_version=1 < CURRENT_SCHEMA_VERSION=2, so the dispatcher's
        # while loop genuinely runs at least once and exercises the
        # `.get(...) is not None` skip-on-empty path against the
        # patched-empty registry -- not a vacuous pass from the loop never
        # executing (which would happen if schema_version >= CURRENT_SCHEMA_VERSION).
        result = migrate_chart(raw, schema_version=1)

    assert result == {"chart_type": "line"}


def test_applies_registered_migrations_in_order():
    calls = []

    def step_a(raw):
        calls.append("a")
        return {**raw, "a": True}

    def step_b(raw):
        calls.append("b")
        return {**raw, "b": True}

    with patch(
        "pandaplot.models.migrations.per_item.chart.PER_ITEM_CHART_MIGRATIONS",
        {0: step_a, 1: step_b},
    ), patch("pandaplot.models.migrations.per_item.chart.CURRENT_SCHEMA_VERSION", 2):
        result = migrate_chart({}, schema_version=0)

    assert calls == ["a", "b"]
    assert result == {"a": True, "b": True}


def test_starts_from_the_given_schema_version_not_zero():
    calls = []

    def step_a(raw):
        calls.append("a")
        return raw

    def step_b(raw):
        calls.append("b")
        return raw

    with patch(
        "pandaplot.models.migrations.per_item.chart.PER_ITEM_CHART_MIGRATIONS",
        {0: step_a, 1: step_b},
    ), patch("pandaplot.models.migrations.per_item.chart.CURRENT_SCHEMA_VERSION", 2):
        migrate_chart({}, schema_version=1)

    assert calls == ["b"]


def test_skips_a_version_with_no_registered_migration():
    calls = []

    def step_b(raw):
        calls.append("b")
        return {**raw, "b": True}

    with patch(
        "pandaplot.models.migrations.per_item.chart.PER_ITEM_CHART_MIGRATIONS",
        {1: step_b},  # nothing registered for version 0
    ), patch("pandaplot.models.migrations.per_item.chart.CURRENT_SCHEMA_VERSION", 2):
        result = migrate_chart({}, schema_version=0)

    assert calls == ["b"]
    assert result == {"b": True}


class TestMigrateChartLegacyToV1:
    """The real legacy->v1 per-item migration: for each series, adds
    series_type + a fully-nested style dict (direct fields, plus a
    "marker" sub-dict for line/scatter and an "error_bars" sub-dict for
    line/scatter/bar), derived from the chart's chart_type and that
    series' own existing flat fields; for each fit, moves its flat
    color/line_style/line_width/alpha fields into a nested style dict.
    This migration strips the old flat fields it copies into style --
    there is no "later sub-phase" relying on their presence, since this
    whole redesign lands as one connected unit (see the function's own
    docstring)."""

    def test_adds_series_type_from_chart_type(self):
        raw = {
            "chart_type": "bar",
            "data_series": [{"dataset_id": "ds1", "x_column": "x", "y_column": "y", "color": "#112233"}],
        }

        migrated = migrate_chart_legacy_to_v1(raw)

        assert migrated["data_series"][0]["series_type"] == "bar"

    def test_extracts_line_style_fields_into_a_style_dict_with_marker_and_error_bars_nested(self):
        raw = {
            "chart_type": "line",
            "data_series": [{
                "dataset_id": "ds1", "x_column": "x", "y_column": "y",
                "color": "#112233", "line_style": "dashed", "line_width": 3.0,
                "marker_style": "square", "marker_size": 5.0,
                "marker_color": "#445566", "marker_edge_color": "#000000", "marker_edge_width": 2.0,
                "fill_enabled": True, "fill_color": "#778899", "fill_alpha": 0.5,
                "fill_orientation": "horizontal", "fill_base": 1.0, "fill_to_index": 2,
                "x_error_column_id": "xe", "y_error_column_id": "ye",
                "error_symmetric": False, "error_direction": "plus", "error_color": "#000",
                "error_cap_size": 4.0,
            }],
        }

        migrated = migrate_chart_legacy_to_v1(raw)

        style = migrated["data_series"][0]["style"]
        assert style == {
            "color": "#112233",
            "line_style": "dashed", "line_width": 3.0,
            "fill_enabled": True, "fill_color": "#778899", "fill_alpha": 0.5,
            "fill_orientation": "horizontal", "fill_base": 1.0, "fill_to_index": 2,
            "marker": {
                "marker_color": "#445566",
                "marker_edge_color": "#000000", "marker_edge_width": 2.0,
                "marker_style": "square", "marker_size": 5.0,
            },
            "error_bars": {
                "x_error_column_id": "xe", "y_error_column_id": "ye",
                "error_symmetric": False, "error_direction": "plus",
                "error_color": "#000", "error_cap_size": 4.0,
            },
        }

    def test_extracts_scatter_style_fields_with_marker_and_error_bars_nested(self):
        raw = {
            "chart_type": "scatter",
            "data_series": [{
                "dataset_id": "ds1", "x_column": "x", "y_column": "y",
                "color": "#112233",
                "marker_style": "square", "marker_size": 5.0,
                "marker_color": "#445566", "marker_edge_color": "#000000", "marker_edge_width": 2.0,
                "x_error_column_id": "xe",
            }],
        }

        migrated = migrate_chart_legacy_to_v1(raw)

        assert migrated["data_series"][0]["style"] == {
            "color": "#112233",
            "marker": {
                "marker_color": "#445566",
                "marker_edge_color": "#000000", "marker_edge_width": 2.0,
                "marker_style": "square", "marker_size": 5.0,
            },
            "error_bars": {"x_error_column_id": "xe"},
        }

    def test_extracts_bar_style_fields_only_no_marker_but_has_error_bars(self):
        raw = {
            "chart_type": "bar",
            "data_series": [{
                "dataset_id": "ds1", "x_column": "x", "y_column": "y",
                "color": "#112233", "line_style": "dashed",  # line_style present but irrelevant to bar
                "x_error_column_id": "xe",
            }],
        }

        migrated = migrate_chart_legacy_to_v1(raw)

        assert migrated["data_series"][0]["style"] == {
            "color": "#112233",
            "error_bars": {"x_error_column_id": "xe"},
        }

    def test_extracts_hist_style_fields_only_no_marker_no_error_bars(self):
        raw = {
            "chart_type": "hist",
            "data_series": [{
                "dataset_id": "ds1", "x_column": "x", "y_column": "y",
                "color": "#112233",
            }],
        }

        migrated = migrate_chart_legacy_to_v1(raw)

        assert migrated["data_series"][0]["style"] == {"color": "#112233"}

    def test_extracts_vector_style_fields_including_nested_columns(self):
        raw = {
            "chart_type": "vector",
            "data_series": [{
                "dataset_id": "ds1", "x_column": "x", "y_column": "y",
                "vector_color": "#abcdef", "vector_scale": 2.0, "vector_width": 0.01,
                "vector_head_width": 4.0, "vector_head_length": 6.0, "vector_head_axis_length": 5.0,
                "vector_colormap": "viridis",
                "u_column_id": "u1", "v_column_id": "v1", "u_column": "u", "v_column": "v",
                "magnitude_column_id": "m1", "magnitude_column": "m",
            }],
        }

        migrated = migrate_chart_legacy_to_v1(raw)

        assert migrated["data_series"][0]["style"] == {
            "vector_color": "#abcdef", "vector_colormap": "viridis",
            "vector_scale": 2.0, "vector_width": 0.01,
            "vector_head_width": 4.0, "vector_head_length": 6.0, "vector_head_axis_length": 5.0,
            "u_column_id": "u1", "v_column_id": "v1", "u_column": "u", "v_column": "v",
            "magnitude_column_id": "m1", "magnitude_column": "m",
        }

    def test_strips_the_old_flat_fields_once_extracted_into_style(self):
        raw = {
            "chart_type": "line",
            "data_series": [{
                "dataset_id": "ds1", "x_column": "x", "y_column": "y",
                "color": "#112233", "marker_color": "#445566", "x_error_column_id": "xe",
            }],
        }

        migrated = migrate_chart_legacy_to_v1(raw)

        series = migrated["data_series"][0]
        assert "color" not in series
        assert "marker_color" not in series
        assert "x_error_column_id" not in series
        # Fields not owned by this migration stay untouched.
        assert series["dataset_id"] == "ds1"
        assert series["x_column"] == "x"
        assert series["y_column"] == "y"

    def test_does_not_mutate_the_input_dict(self):
        raw = {
            "chart_type": "line",
            "data_series": [{"dataset_id": "ds1", "x_column": "x", "y_column": "y", "color": "#112233"}],
        }

        migrate_chart_legacy_to_v1(raw)

        assert "series_type" not in raw["data_series"][0]
        assert "style" not in raw["data_series"][0]
        assert raw["data_series"][0]["color"] == "#112233"

    def test_handles_a_chart_with_no_series(self):
        raw = {"chart_type": "line", "data_series": []}

        migrated = migrate_chart_legacy_to_v1(raw)

        assert migrated["data_series"] == []

    def test_defaults_missing_data_series_key_to_empty(self):
        raw = {"chart_type": "line"}

        migrated = migrate_chart_legacy_to_v1(raw)

        assert migrated["data_series"] == []

    def test_moves_fit_style_fields_into_a_nested_style_dict(self):
        raw = {
            "chart_type": "line",
            "data_series": [],
            "fit_data": [{
                "source_dataset_id": "ds1", "fit_type": "linear",
                "color": "#112233", "line_style": "dotted", "line_width": 3.0, "alpha": 0.5,
                "confidence_lower": [1.0], "confidence_upper": [2.0],
            }],
        }

        migrated = migrate_chart_legacy_to_v1(raw)

        fit = migrated["fit_data"][0]
        assert fit["style"] == {"color": "#112233", "line_style": "dotted", "line_width": 3.0, "alpha": 0.5}
        assert "color" not in fit
        assert "line_style" not in fit
        assert "line_width" not in fit
        assert "alpha" not in fit
        assert fit["confidence_lower"] == [1.0]  # untouched
        assert fit["confidence_upper"] == [2.0]  # untouched

    def test_handles_a_fit_missing_some_style_fields(self):
        raw = {"chart_type": "line", "data_series": [],
               "fit_data": [{"source_dataset_id": "ds1", "fit_type": "linear"}]}

        migrated = migrate_chart_legacy_to_v1(raw)

        assert migrated["fit_data"][0]["style"] == {}

    def test_handles_a_chart_with_no_fit_data(self):
        raw = {"chart_type": "line", "data_series": []}

        migrated = migrate_chart_legacy_to_v1(raw)

        assert migrated["fit_data"] == []

    def test_does_not_mutate_the_input_fit_dict(self):
        raw = {
            "chart_type": "line",
            "data_series": [],
            "fit_data": [{"source_dataset_id": "ds1", "fit_type": "linear", "color": "#112233"}],
        }

        migrate_chart_legacy_to_v1(raw)

        assert "style" not in raw["fit_data"][0]
        assert raw["fit_data"][0]["color"] == "#112233"


def test_style_field_names_match_the_real_style_dataclasses():
    """Guards against the migration's _DIRECT_STYLE_FIELDS_BY_CHART_TYPE/
    _MARKER_FIELDS_BY_CHART_TYPE/_ERROR_BAR_FIELDS drifting out of sync
    with the real style dataclasses -- a drift here raises a TypeError at
    project-load time that ProjectDataManager._load_item()'s bare except
    silently swallows, dropping the whole chart.

    Since a style dataclass composes marker/error_bars as single nested
    fields, a flat dataclasses.fields() comparison only sees the
    top-level names; direct fields are checked against those (minus
    "marker"/"error_bars"), while marker/error-bar fields are checked
    separately against MarkerStyle/ErrorBarConfig.

    COLORMAP/HEATMAP are excluded: they were added after
    CURRENT_SCHEMA_VERSION was bumped to 1, so no legacy (schema_version
    0) project file can contain them, and this migration only runs for
    schema_version 0 data. A separate assertion locks the two dicts free
    of entries for them, so no one adds placeholder entries that legacy
    data will never exercise."""
    import dataclasses

    from pandaplot.models.chart.error_bar_config import ErrorBarConfig
    from pandaplot.models.chart.marker_style import MarkerStyle
    from pandaplot.models.chart.series_type import SeriesType
    from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
    from pandaplot.models.migrations.per_item.chart import (
        _DIRECT_STYLE_FIELDS_BY_CHART_TYPE,
        _ERROR_BAR_FIELDS,
        _MARKER_FIELDS_BY_CHART_TYPE,
    )

    # Chart types that predate the typed-style migration architecture --
    # i.e. could genuinely have a schema_version-0 project file saved by
    # a real user, with legacy flat fields for this migration to convert.
    # Derived directly from the production dicts' own keys (rather than a
    # hand-maintained parallel list) so this test can't silently stop
    # covering a type if a future contributor adds it to those dicts but
    # forgets to update a separate list here.
    _PRE_MIGRATION_SERIES_TYPES = {
        SeriesType(chart_type)
        for chart_type in set(_DIRECT_STYLE_FIELDS_BY_CHART_TYPE) | set(_MARKER_FIELDS_BY_CHART_TYPE)
    }
    assert SeriesType.COLORMAP not in _PRE_MIGRATION_SERIES_TYPES
    assert SeriesType.HEATMAP not in _PRE_MIGRATION_SERIES_TYPES
    assert "colormap" not in _DIRECT_STYLE_FIELDS_BY_CHART_TYPE
    assert "heatmap" not in _DIRECT_STYLE_FIELDS_BY_CHART_TYPE
    assert "colormap" not in _MARKER_FIELDS_BY_CHART_TYPE
    assert "heatmap" not in _MARKER_FIELDS_BY_CHART_TYPE

    marker_field_names = {f.name for f in dataclasses.fields(MarkerStyle)}
    error_bar_field_names = {f.name for f in dataclasses.fields(ErrorBarConfig)}

    for series_type in _PRE_MIGRATION_SERIES_TYPES:
        spec = SERIES_TYPE_SPECS[series_type]
        top_level_field_names = {f.name for f in dataclasses.fields(spec.style_cls)}
        expected_direct = top_level_field_names - {"marker", "error_bars"}
        actual_direct = set(_DIRECT_STYLE_FIELDS_BY_CHART_TYPE[series_type.value])
        assert actual_direct == expected_direct, f"{series_type.value}: {actual_direct} != {expected_direct}"

        has_marker = "marker" in top_level_field_names
        assert has_marker == (series_type.value in _MARKER_FIELDS_BY_CHART_TYPE)
        if has_marker:
            actual_marker = set(_MARKER_FIELDS_BY_CHART_TYPE[series_type.value])
            assert actual_marker == marker_field_names, f"{series_type.value}: {actual_marker} != {marker_field_names}"

        has_error_bars = "error_bars" in top_level_field_names
        if has_error_bars:
            assert set(_ERROR_BAR_FIELDS).issubset(error_bar_field_names), (
                f"{set(_ERROR_BAR_FIELDS)} not a subset of {error_bar_field_names}"
            )


def test_fit_style_fields_are_a_subset_of_the_real_fit_style_dataclass():
    """Guards against the migration's _FIT_STYLE_FIELDS drifting out of
    sync with FitStyle -- a drift (e.g. a rename) would raise a TypeError
    at project-load time, silently swallowed by
    ProjectDataManager._load_item()'s bare except, dropping the chart.

    Subset (not equality) is correct: FitStyle also has
    band_fill_enabled/band_fill_alpha/band_color, deliberately absent
    from _FIT_STYLE_FIELDS since old data never had them and should fall
    through to FitStyle's own defaults."""
    import dataclasses

    from pandaplot.models.chart.fit_style import FitStyle
    from pandaplot.models.migrations.per_item.chart import _FIT_STYLE_FIELDS

    real_field_names = {f.name for f in dataclasses.fields(FitStyle)}
    assert set(_FIT_STYLE_FIELDS).issubset(real_field_names), (
        f"{set(_FIT_STYLE_FIELDS)} not a subset of {real_field_names}"
    )
