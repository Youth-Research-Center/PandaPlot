"""Tests for the wizard's per-chart-type column-role requirements."""
import pytest

from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS, get_chart_type_spec


def test_line_requires_only_y():
    spec = get_chart_type_spec("line")
    assert spec.roles == ("x", "y")
    assert spec.required_roles == ("y",)
    assert spec.supports_error_bars is True


def test_scatter_requires_only_y():
    spec = get_chart_type_spec("scatter")
    assert spec.required_roles == ("y",)
    assert spec.supports_error_bars is True


def test_bar_requires_only_y():
    spec = get_chart_type_spec("bar")
    assert spec.roles == ("x", "y")
    assert spec.required_roles == ("y",)
    assert spec.supports_error_bars is True


def test_histogram_requires_values_and_has_no_error_bars():
    spec = get_chart_type_spec("hist")
    assert spec.roles == ("values",)
    assert spec.required_roles == ("values",)
    assert spec.supports_error_bars is False


def test_vector_requires_x_y_u_v():
    spec = get_chart_type_spec("vector")
    assert spec.roles == ("x", "y", "u", "v", "magnitude")
    assert spec.required_roles == ("x", "y", "u", "v")
    assert spec.supports_error_bars is False


def test_unknown_chart_type_raises_value_error():
    # Changed from KeyError to ValueError: get_chart_type_spec raises via
    # ChartType(chart_type)'s own coercion, not a dict lookup -- an
    # intentional, disclosed exception-type change (see chart_type_spec.py's
    # get_chart_type_spec docstring), not a bug.
    with pytest.raises(ValueError):
        get_chart_type_spec("violin")


def test_every_chart_type_is_registered():
    assert set(CHART_TYPE_SPECS.keys()) == set(ChartType)
