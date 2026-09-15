from dataclasses import asdict

from pandaplot.models.chart.axis_config import AxisConfig


def test_defaults():
    axis = AxisConfig()
    assert axis.label == ""
    assert axis.scale == "linear"
    assert axis.auto_limits is True
    assert axis.min == 0.0
    assert axis.max == 1.0
    assert axis.show_grid is True
    assert axis.side is None
    assert axis.label_rotation == 0.0
    assert axis.spine_color == "#000000"


def test_is_a_plain_dataclass_round_trippable_via_asdict_and_kwargs():
    axis = AxisConfig(label="Time (s)", min=-5.0, max=5.0, side="left", label_rotation=90.0)
    data = asdict(axis)
    restored = AxisConfig(**data)
    assert restored == axis
