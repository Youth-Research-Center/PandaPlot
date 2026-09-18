"""Tests for the per-item chart migration dispatcher.

PER_ITEM_CHART_MIGRATIONS has two real entries: migrate_chart_legacy_to_v1
(schema_version 0 -> 1, see TestMigrateChartLegacyToV1 below) and
migrate_chart_v1_to_v2 (schema_version 1 -> 2, see TestMigrateChartV1ToV2
-- nests axis-prefixed flat config keys like "x_min"/"show_grid_x" under
config["x"]/["y"]/["y2"]/["z"], see #146 PR2). The dispatcher-loop tests
below patch the registry to whatever shape each scenario needs -- pinning
down migrate_chart's loop behavior in isolation from the real migration
content, the same way test_runner.py does for the cross-item runner.
"""
from unittest.mock import patch

from pandaplot.models.migrations.per_item.chart import (
    migrate_chart,
    migrate_chart_legacy_to_v1,
    migrate_chart_v1_to_v2,
)


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


class TestMigrateChartV1ToV2:
    """Nests every axis-prefixed flat config key ("x_min", "y2_tick_mode",
    "show_grid_x") under config["x"]/["y"]/["y2"]/["z"] -- see #146 PR2,
    ChartConfig.x/.y/.y2/.z are now typed AxisConfig instances instead of
    flat dict keys."""

    def test_nests_axis_prefixed_config_keys(self):
        raw = {
            "config": {
                "title": "My Chart",
                "show_legend": True,
                "x_label": "Time",
                "x_min": -5.0,
                "x_max": 5.0,
                "show_grid_x": False,
                "y_scale": "log",
                "y_log_base": 2.0,
                "y2_side": "left",
                "z_font_size": 14,
            },
            "style": {},
            "data_series": [],
            "fit_data": [],
        }

        migrated = migrate_chart_v1_to_v2(raw)

        config = migrated["config"]
        assert config["title"] == "My Chart"
        assert config["show_legend"] is True
        assert "x_label" not in config
        assert "x_min" not in config
        assert "show_grid_x" not in config
        assert "y_scale" not in config
        assert "y2_side" not in config
        assert config["x"] == {"label": "Time", "min": -5.0, "max": 5.0, "show_grid": False}
        assert config["y"] == {"scale": "log", "log_base": 2.0}
        assert config["y2"] == {"side": "left"}
        assert config["z"] == {"font_size": 14}

    def test_handles_a_chart_with_no_axis_keys_at_all(self):
        raw = {"config": {"title": "Empty"}, "style": {}, "data_series": [], "fit_data": []}

        migrated = migrate_chart_v1_to_v2(raw)

        assert migrated["config"] == {"title": "Empty", "x": {}, "y": {}, "y2": {}, "z": {}}

    def test_leaves_a_chart_with_no_config_key_untouched(self):
        raw = {"data_series": [], "fit_data": []}

        migrated = migrate_chart_v1_to_v2(raw)

        assert "config" not in migrated

    def test_does_not_mutate_the_input_dict(self):
        raw = {"config": {"x_min": -5.0}, "data_series": [], "fit_data": []}

        migrate_chart_v1_to_v2(raw)

        assert raw["config"] == {"x_min": -5.0}


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
    data will never exercise.

    Direct fields are checked for exact equality against the real dataclass
    minus an explicit _POST_MIGRATION_FIELDS exclusion set, not a bare
    subset: a style dataclass field added after this migration's field
    lists were written (e.g. LineSeriesStyle/ScatterSeriesStyle/
    BarSeriesStyle's show_value_labels and the value_label_* fields, #125)
    can't appear in any genuinely legacy schema_version-0 file either, so it
    correctly falls through to the dataclass's own default via
    style_cls(**style_dict) instead of needing to be hand-added to a list
    meant to describe the old flat format -- but it must be named in
    _POST_MIGRATION_FIELDS explicitly, so accidentally dropping a genuinely
    legacy field from _DIRECT_STYLE_FIELDS_BY_CHART_TYPE (which a bare
    subset check can't catch) still fails this test."""
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

    # Fields added to a style dataclass after this migration's field lists
    # were written (#125) -- no legacy schema_version-0 file can contain
    # them, so they're excluded from the equality check below rather than
    # weakening it to a subset check for every field.
    _POST_MIGRATION_FIELDS = {
        "show_value_labels", "value_label_mode", "value_label_show_arrow",
        "value_label_offset_x", "value_label_offset_y", "value_label_text_color",
        "value_label_bg_color", "value_label_bg_alpha",
    }

    for series_type in _PRE_MIGRATION_SERIES_TYPES:
        spec = SERIES_TYPE_SPECS[series_type]
        top_level_field_names = {f.name for f in dataclasses.fields(spec.style_cls)}
        expected_direct = top_level_field_names - {"marker", "error_bars"} - _POST_MIGRATION_FIELDS
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
    through to FitStyle's own defaults.

    "alpha" is excluded from the subset check: #304 moved fit opacity
    off FitStyle onto the generic DataSeries.alpha field every other
    series type already uses. migrate_chart_legacy_to_v1 (schema 0->1)
    still nests legacy flat "alpha" into style["alpha"] here -- migrate_
    chart_v2_to_v3 pulls it back out into the series' top-level "alpha"
    before FitStyle(**style_dict) is ever constructed, so this is a
    genuinely transient field, not a drift bug."""
    import dataclasses

    from pandaplot.models.chart.fit_style import FitStyle
    from pandaplot.models.migrations.per_item.chart import _FIT_STYLE_FIELDS

    real_field_names = {f.name for f in dataclasses.fields(FitStyle)} | {"alpha"}
    assert set(_FIT_STYLE_FIELDS).issubset(real_field_names), (
        f"{set(_FIT_STYLE_FIELDS)} not a subset of {real_field_names}"
    )


def test_migrate_chart_v2_to_v3_folds_fit_data_into_data_series():
    from pandaplot.models.migrations.per_item.chart import migrate_chart_v2_to_v3

    raw = {
        "chart_type": "line",
        "data_series": [{"dataset_id": "ds1", "series_type": "line", "style": {}}],
        "fit_data": [{
            "source_dataset_id": "ds1",
            "source_x_column_id": "xid", "source_y_column_id": "yid",
            "source_x_column": "X", "source_y_column": "Y",
            "fit_type": "linear",
            "x_data": [1.0, 2.0], "y_data": [3.0, 4.0],
            "label": "My Fit", "visible": True,
            "fit_params": {"a": 1.0}, "fit_stats": {"r_squared": 0.9},
            "confidence_lower": [0.5, 1.5], "confidence_upper": [1.5, 2.5],
            "confidence_lower_column_id": "", "confidence_upper_column_id": "",
            "is_manual": False,
            "style": {
                "color": "#ff7f0e", "line_style": "dashed", "line_width": 2.0,
                "alpha": 0.8,
            },
        }],
    }

    migrated = migrate_chart_v2_to_v3(raw)

    assert "fit_data" not in migrated
    assert len(migrated["data_series"]) == 2
    fit_entry = migrated["data_series"][1]
    assert fit_entry["series_type"] == "fit"
    assert fit_entry["dataset_id"] == "ds1"
    assert fit_entry["x_column_id"] == "xid"
    assert fit_entry["y_column_id"] == "yid"
    assert fit_entry["alpha"] == 0.8  # pulled up from style.alpha
    assert "alpha" not in fit_entry["style"]
    assert fit_entry["precomputed_x_data"] == [1.0, 2.0]
    assert fit_entry["precomputed_y_data"] == [3.0, 4.0]
    assert fit_entry["style"]["fit_type"] == "linear"
    assert fit_entry["style"]["fit_params"] == {"a": 1.0}
    assert fit_entry["style"]["confidence_lower"] == [0.5, 1.5]
    assert fit_entry["y_axis"] == "primary"


def test_migrate_chart_dispatches_through_v2_to_v3(monkeypatch=None):
    from pandaplot.models.migrations.per_item.chart import migrate_chart

    raw = {
        "chart_type": "line", "data_series": [],
        "fit_data": [{
            "source_dataset_id": "ds1", "fit_type": "linear",
            "x_data": [1.0], "y_data": [2.0], "label": "Fit",
            "style": {"color": "#000", "line_style": "solid", "line_width": 1.0, "alpha": 1.0},
        }],
    }
    result = migrate_chart(raw, schema_version=2)
    assert "fit_data" not in result
    assert len(result["data_series"]) == 1


def test_migrate_chart_runs_the_full_schema_0_to_v3_chain_for_a_populated_fit():
    """Regression/coverage test for final-review Important finding #4: a
    coverage gap, not a known defect -- the reviewer manually verified the
    chain composes, but nothing pinned it down end to end. Runs a genuinely
    legacy (schema_version=0) chart dict -- flat color/line_style/alpha
    fields directly on the fit_data entry, pre-dating any nested "style"
    dict -- through migrate_chart(raw, schema_version=0), exercising all
    three migrations in sequence (legacy_to_v1 nests the flat fit style
    fields; v1_to_v2 nests axis-prefixed config keys; v2_to_v3 folds
    fit_data into data_series)."""
    from pandaplot.models.migrations.per_item.chart import migrate_chart

    raw = {
        "chart_type": "line",
        "data_series": [{"dataset_id": "ds1", "x_column": "x", "y_column": "y", "color": "#112233"}],
        "fit_data": [{
            "source_dataset_id": "ds1",
            "source_x_column_id": "xid", "source_y_column_id": "yid",
            "source_x_column": "X", "source_y_column": "Y",
            "fit_type": "linear",
            "x_data": [1.0, 2.0], "y_data": [3.0, 4.0],
            "label": "My Fit", "visible": True,
            # Flat, pre-nested-style fields -- the schema-0 shape.
            "color": "#112233", "line_style": "dotted", "line_width": 3.0, "alpha": 0.5,
            "confidence_lower": [0.5, 1.5], "confidence_upper": [1.5, 2.5],
            "fit_params": {"a": 1.0}, "fit_stats": {"r_squared": 0.9},
        }],
        "config": {
            "title": "Legacy Chart With A Fit",
            "x_min": -5.0, "x_max": 5.0,
        },
        "style": {},
    }

    migrated = migrate_chart(raw, schema_version=0)

    # v2_to_v3's effect: no more separate fit_data list.
    assert "fit_data" not in migrated
    assert len(migrated["data_series"]) == 2
    fit_entry = migrated["data_series"][1]
    assert fit_entry["series_type"] == "fit"
    assert fit_entry["dataset_id"] == "ds1"
    assert fit_entry["x_column_id"] == "xid"
    assert fit_entry["y_column_id"] == "yid"
    assert fit_entry["precomputed_x_data"] == [1.0, 2.0]
    assert fit_entry["precomputed_y_data"] == [3.0, 4.0]
    # alpha ended up at the series' top level, not nested in style.
    assert fit_entry["alpha"] == 0.5
    assert "alpha" not in fit_entry["style"]
    # The rest of the flat fields correctly landed in style.
    style = fit_entry["style"]
    assert style["color"] == "#112233"
    assert style["line_style"] == "dotted"
    assert style["line_width"] == 3.0
    assert style["fit_type"] == "linear"
    assert style["fit_params"] == {"a": 1.0}
    assert style["fit_stats"] == {"r_squared": 0.9}
    assert style["confidence_lower"] == [0.5, 1.5]
    assert style["confidence_upper"] == [1.5, 2.5]
    # v1_to_v2's effect on the chart's own config (unrelated to the fit,
    # but confirms the full chain -- not just v2_to_v3 -- actually ran).
    assert migrated["config"]["x"] == {"min": -5.0, "max": 5.0}
    assert "x_min" not in migrated["config"]
    # v1_to_v1's effect on the plain data series.
    assert migrated["data_series"][0]["style"]["color"] == "#112233"
