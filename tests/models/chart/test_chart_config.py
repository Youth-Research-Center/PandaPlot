import pytest

from pandaplot.models.chart.axis_config import AxisConfig
from pandaplot.models.chart.chart_config import ChartConfig


def test_defaults_match_current_behavior():
    config = ChartConfig()
    assert config.title == ""
    assert config.show_legend is True
    assert config.legend_position == "upper right"
    assert config.grid_alpha == 0.3
    assert config.width_cm is None
    assert config.colormap == "viridis"


def test_typed_field_attribute_access():
    config = ChartConfig()
    config.title = "My Chart"
    assert config.title == "My Chart"


def test_to_dict_round_trip_known_fields_only():
    config = ChartConfig(title="Foo", show_legend=False, grid_alpha=0.7)
    data = config.to_dict()
    restored = ChartConfig.from_dict(data)
    assert restored.title == "Foo"
    assert restored.show_legend is False
    assert restored.grid_alpha == 0.7


def test_from_dict_ignores_unknown_top_level_keys_gracefully_via_legacy():
    # A genuinely unrecognized key (not a ChartConfig field, not an
    # axis-prefixed AxisConfig field) must not raise and must round-trip
    # unchanged -- the forward-compatibility safety net, not a home for
    # known keys (see test_flat_axis_prefixed_key_still_works_via_the_
    # dict_style_shim for those).
    data = {"title": "Foo", "some_future_key": 5.0}
    config = ChartConfig.from_dict(data)
    assert config.title == "Foo"
    assert config.get("some_future_key") == 5.0
    round_tripped = config.to_dict()
    assert round_tripped["some_future_key"] == 5.0
    assert round_tripped["title"] == "Foo"


def test_legacy_shim_get_getitem_setitem_update():
    config = ChartConfig()
    # known field via dict-style API (used by not-yet-migrated call sites)
    config["title"] = "Bar"
    assert config.title == "Bar"
    assert config["title"] == "Bar"
    assert config.get("title") == "Bar"
    # unknown/legacy field via dict-style API
    config["some_future_key"] = 1.5
    assert config["some_future_key"] == 1.5
    assert config.get("some_future_key") == 1.5
    assert config.get("another_unknown_key", 9.0) == 9.0
    with pytest.raises(KeyError):
        _ = config["another_unknown_key"]
    config.update({"title": "Baz", "another_unknown_key": 2.5})
    assert config.title == "Baz"
    assert config["another_unknown_key"] == 2.5


def test_contains_checks_both_typed_fields_and_legacy():
    config = ChartConfig()
    assert "title" in config
    assert "some_future_key" not in config
    config["some_future_key"] = 1.0
    assert "some_future_key" in config


def test_unknown_field_via_attribute_access_still_raises():
    # Real dataclass attribute access (not the dict-style shim) must behave
    # like a normal typed object -- no silent typo tolerance.
    config = ChartConfig()
    with pytest.raises(AttributeError):
        _ = config.xmin  # typo for x_min -- and x_min itself isn't a real attribute either


def test_axis_fields_have_correct_per_axis_defaults():
    config = ChartConfig()
    assert isinstance(config.x, AxisConfig)
    assert config.x.side is None
    assert config.x.label_rotation == 0.0
    assert config.y.side == "left"
    assert config.y.label_rotation == 90.0
    assert config.y2.side == "right"
    assert config.y2.label_rotation == 90.0
    assert config.z.side is None
    assert config.z.label_rotation == 0.0


def test_axis_instances_are_independent():
    config = ChartConfig()
    config.x.min = 5.0
    assert config.y.min == 0.0


def test_to_dict_nests_axis_config_and_from_dict_reconstructs_it():
    config = ChartConfig()
    config.x.min = -5.0
    config.x.label = "Time (s)"
    config.y2.tick_mode = "count"
    data = config.to_dict()
    assert data["x"]["min"] == -5.0
    assert data["x"]["label"] == "Time (s)"
    assert data["y2"]["tick_mode"] == "count"
    restored = ChartConfig.from_dict(data)
    assert restored.x.min == -5.0
    assert restored.x.label == "Time (s)"
    assert restored.y2.tick_mode == "count"
    assert restored.y.side == "left"  # untouched axis keeps its own default


def test_flat_axis_prefixed_key_still_works_via_the_dict_style_shim():
    # Existing test fixtures and Chart.update_config() call sites use flat
    # keys like "y2_tick_mode" as shorthand -- these must keep working
    # after axis fields become real AxisConfig attributes instead of
    # falling into `_legacy`.
    config = ChartConfig()
    config["y2_tick_mode"] = "count"
    assert config.y2.tick_mode == "count"
    assert config["y2_tick_mode"] == "count"
    assert config.get("y2_tick_mode") == "count"
    assert "y2_tick_mode" in config

    config["show_grid_x"] = False
    assert config.x.show_grid is False
    assert config.get("show_grid_x") is False

    config.update({"x_min": -1.0, "y_label_color": "#ff0000"})
    assert config.x.min == -1.0
    assert config.y.label_color == "#ff0000"


def test_unrecognized_flat_key_still_falls_back_to_legacy_bucket():
    # Genuinely unknown keys (not a ChartConfig field, not an axis-prefixed
    # AxisConfig field) still round-trip through `_legacy`, same as before
    # -- this is the forward-compatibility safety net, not a place for
    # known keys to hide.
    config = ChartConfig.from_dict({"some_future_key": 42})
    assert config.get("some_future_key") == 42
    assert config.to_dict()["some_future_key"] == 42
