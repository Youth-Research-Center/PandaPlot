"""Per-item migrations for chart raw dicts.

Pure dict -> dict transforms, run before Chart.from_dict() constructs the
object -- unlike cross-item migrations (see migrations/cross_item/),
these cannot look up another item's data (e.g. a dataset), only reshape
the chart's own dict.
"""
from typing import Callable

from pandaplot.models.migrations.schema_version import CURRENT_SCHEMA_VERSION

# Which of a legacy series' flat fields belong under style.marker, per
# chart type -- only line/scatter ever had marker fields.
_MARKER_FIELDS_BY_CHART_TYPE: dict[str, tuple[str, ...]] = {
    "line": ("marker_color", "marker_edge_color", "marker_edge_width", "marker_style", "marker_size"),
    "scatter": ("marker_color", "marker_edge_color", "marker_edge_width", "marker_style", "marker_size"),
}

# Which of a legacy series' flat fields belong under style.error_bars,
# per chart type -- line/scatter/bar all supported error bars.
_ERROR_BAR_FIELDS = (
    "x_error_column_id", "y_error_column_id",
    "x_error_minus_column_id", "y_error_minus_column_id",
    "x_error_column", "y_error_column",
    "x_error_minus_column", "y_error_minus_column",
    "error_symmetric", "error_direction", "error_color", "error_cap_size",
)
_ERROR_BAR_CHART_TYPES = ("line", "scatter", "bar")

# Which of a legacy series' flat fields belong directly on style (not
# nested further), per chart type.
_DIRECT_STYLE_FIELDS_BY_CHART_TYPE: dict[str, tuple[str, ...]] = {
    "line": ("color", "line_style", "line_width", "fill_enabled", "fill_color", "fill_alpha", "fill_orientation", "fill_base", "fill_to_index"),
    "scatter": ("color",),
    "bar": ("color",),
    "hist": ("color",),
    "vector": (
        "vector_color", "vector_colormap", "vector_scale", "vector_width",
        "vector_head_width", "vector_head_length", "vector_head_axis_length",
        "u_column_id", "v_column_id", "u_column", "v_column",
        "magnitude_column_id", "magnitude_column",
    ),
}

_FIT_STYLE_FIELDS = ("color", "line_style", "line_width", "alpha")

# Every flat field this migration extracts into a series' nested style,
# across all chart types -- used to strip the now-redundant flat keys
# once they've been copied into style (see migrate_chart_legacy_to_v1's
# docstring for why this migration removes them, unlike the original
# v1->v2 it replaces).
_ALL_EXTRACTED_SERIES_FIELDS = frozenset(
    field
    for fields in _DIRECT_STYLE_FIELDS_BY_CHART_TYPE.values()
    for field in fields
) | frozenset(
    field
    for fields in _MARKER_FIELDS_BY_CHART_TYPE.values()
    for field in fields
) | frozenset(_ERROR_BAR_FIELDS)


def migrate_chart_legacy_to_v1(raw: dict) -> dict:
    """Bring a pre-this-refactor chart dict (schema_version absent/0) up
    to the current typed shape: each series gets a series_type +
    fully-nested style (direct fields, plus "marker" for line/scatter
    and "error_bars" for line/scatter/bar); each fit gets a nested
    style. This replaces what were previously two separate migrations
    (v1->v2 for series, v2->v3 for fits) -- there's exactly one prior
    shape in the wild (this schema-versioning system never shipped to a
    real user), so there's nothing intermediate to preserve.

    Unlike the original v1->v2, which left the old flat fields in place
    for a later cleanup once all consumers read the nested fields, this
    migration strips them immediately -- that cleanup already happened
    as part of this same redesign, so the flat duplicates are dead
    weight from the start.
    """
    chart_type = raw.get("chart_type", "line")
    direct_fields = _DIRECT_STYLE_FIELDS_BY_CHART_TYPE.get(chart_type, _DIRECT_STYLE_FIELDS_BY_CHART_TYPE["line"])
    marker_fields = _MARKER_FIELDS_BY_CHART_TYPE.get(chart_type, ())

    migrated_series = []
    for series in raw.get("data_series", []):
        new_series = dict(series)
        new_series["series_type"] = chart_type
        style = {name: series[name] for name in direct_fields if name in series}
        if marker_fields:
            style["marker"] = {name: series[name] for name in marker_fields if name in series}
        if chart_type in _ERROR_BAR_CHART_TYPES:
            style["error_bars"] = {name: series[name] for name in _ERROR_BAR_FIELDS if name in series}
        new_series["style"] = style
        for name in _ALL_EXTRACTED_SERIES_FIELDS:
            new_series.pop(name, None)
        migrated_series.append(new_series)

    migrated_fits = []
    for fit in raw.get("fit_data", []):
        new_fit = dict(fit)
        new_fit["style"] = {name: fit[name] for name in _FIT_STYLE_FIELDS if name in fit}
        for name in _FIT_STYLE_FIELDS:
            new_fit.pop(name, None)
        migrated_fits.append(new_fit)

    new_raw = dict(raw)
    new_raw["data_series"] = migrated_series
    new_raw["fit_data"] = migrated_fits
    return new_raw


# Every AxisConfig field name, used by migrate_chart_v1_to_v2 to recognize
# a flat key like "y2_tick_mode" as belonging under the nested "y2" dict.
# Kept independent of chart_config.py's own _resolve_axis_key (that one
# runs against live ChartConfig/AxisConfig objects at read/write time;
# this one runs against a raw, pre-object dict, same separation this
# module already keeps between migrate_chart_legacy_to_v1 and the live
# DataSeries/style classes).
_AXIS_CONFIG_FIELDS = (
    "label", "scale", "auto_limits", "min", "max", "tick_mode", "tick_count",
    "tick_step", "tick_format", "tick_format_custom", "font_size", "side",
    "log_base", "tick_direction", "minor_ticks", "minor_tick_direction",
    "show_minor_grid", "font_family", "title_bold", "title_italic",
    "label_color", "match_x_label_color", "label_rotation",
    "tick_label_font_size", "tick_label_font_family", "tick_label_bold",
    "tick_label_italic", "tick_label_color", "tick_label_rotation",
    "match_x_colors", "spine_color", "major_tick_color", "minor_tick_color",
)
_AXIS_CONFIG_PREFIXES = ("x", "y", "y2", "z")


def migrate_chart_v1_to_v2(raw: dict) -> dict:
    """Nest every axis-prefixed flat config key ("x_min", "y2_tick_mode",
    "show_grid_x") under config["x"]/["y"]/["y2"]/["z"] (see #146, PR2 --
    ChartConfig.x/.y/.y2/.z are now typed AxisConfig instances instead of
    flat dict keys). A chart with no "config" key at all (shouldn't happen
    post-migrate_chart_legacy_to_v1, but defensive) is left untouched --
    Chart.__init__ seeds fresh AxisConfig defaults either way.
    """
    if "config" not in raw:
        return raw

    old_config = raw["config"]
    new_config = {}
    nested: dict[str, dict] = {p: {} for p in _AXIS_CONFIG_PREFIXES}

    for key, value in old_config.items():
        if key.startswith("show_grid_"):
            prefix = key[len("show_grid_"):]
            if prefix in _AXIS_CONFIG_PREFIXES:
                nested[prefix]["show_grid"] = value
                continue
        matched = False
        for prefix in _AXIS_CONFIG_PREFIXES:
            candidate = prefix + "_"
            if key.startswith(candidate) and key[len(candidate):] in _AXIS_CONFIG_FIELDS:
                nested[prefix][key[len(candidate):]] = value
                matched = True
                break
        if not matched:
            new_config[key] = value

    for prefix in _AXIS_CONFIG_PREFIXES:
        new_config[prefix] = nested[prefix]

    new_raw = dict(raw)
    new_raw["config"] = new_config
    return new_raw


PER_ITEM_CHART_MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    0: migrate_chart_legacy_to_v1,
    1: migrate_chart_v1_to_v2,
}


def migrate_chart(raw: dict, schema_version: int) -> dict:
    while schema_version < CURRENT_SCHEMA_VERSION:
        migrate = PER_ITEM_CHART_MIGRATIONS.get(schema_version)
        if migrate is not None:
            raw = migrate(raw)
        schema_version += 1
    return raw
