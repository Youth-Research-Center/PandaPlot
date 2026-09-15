import pytest

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
    # A key belonging to PR2 scope (axis-prefixed) must not raise and must
    # round-trip unchanged, since to_dict()/from_dict() must not alter the
    # persisted shape of not-yet-typed keys.
    data = {"title": "Foo", "x_min": 5.0, "x_label_color": "#ff0000"}
    config = ChartConfig.from_dict(data)
    assert config.title == "Foo"
    assert config.get("x_min") == 5.0
    assert config["x_label_color"] == "#ff0000"
    round_tripped = config.to_dict()
    assert round_tripped["x_min"] == 5.0
    assert round_tripped["x_label_color"] == "#ff0000"
    assert round_tripped["title"] == "Foo"


def test_legacy_shim_get_getitem_setitem_update():
    config = ChartConfig()
    # known field via dict-style API (used by not-yet-migrated call sites)
    config["title"] = "Bar"
    assert config.title == "Bar"
    assert config["title"] == "Bar"
    assert config.get("title") == "Bar"
    # unknown/legacy field via dict-style API
    config["x_min"] = 1.5
    assert config["x_min"] == 1.5
    assert config.get("x_min") == 1.5
    assert config.get("y_min", 9.0) == 9.0
    with pytest.raises(KeyError):
        _ = config["y_min"]
    config.update({"title": "Baz", "y_min": 2.5})
    assert config.title == "Baz"
    assert config["y_min"] == 2.5


def test_unknown_field_via_attribute_access_still_raises():
    # Real dataclass attribute access (not the dict-style shim) must behave
    # like a normal typed object -- no silent typo tolerance.
    config = ChartConfig()
    with pytest.raises(AttributeError):
        _ = config.xmin  # typo for x_min -- and x_min itself isn't a real attribute either
