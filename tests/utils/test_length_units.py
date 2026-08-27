"""Unit tests for chart-size measurement-unit conversion helpers."""
from __future__ import annotations

import pytest

from pandaplot.models.state.config import LengthUnit
from pandaplot.utils.length_units import (
    format_size,
    from_cm,
    quantize_cm,
    to_cm,
    unit_bounds,
    unit_decimals,
    unit_step,
    unit_suffix,
)


def test_to_cm_and_from_cm_identity_for_cm():
    assert to_cm(20.0, LengthUnit.CM) == 20.0
    assert from_cm(20.0, LengthUnit.CM) == 20.0


def test_cm_to_mm_conversion():
    assert to_cm(200.0, LengthUnit.MM) == pytest.approx(20.0)
    assert from_cm(20.0, LengthUnit.MM) == pytest.approx(200.0)


def test_cm_to_inch_conversion():
    assert to_cm(1.0, LengthUnit.IN) == pytest.approx(2.54)
    assert from_cm(2.54, LengthUnit.IN) == pytest.approx(1.0)


def test_round_trip_through_each_unit():
    for unit in LengthUnit:
        assert from_cm(to_cm(10.0, unit), unit) == pytest.approx(10.0)


def test_unit_display_metadata():
    assert unit_suffix(LengthUnit.CM) == " cm"
    assert unit_suffix(LengthUnit.MM) == " mm"
    assert unit_suffix(LengthUnit.IN) == " in"
    assert unit_decimals(LengthUnit.CM) == 1
    assert unit_decimals(LengthUnit.MM) == 0
    assert unit_decimals(LengthUnit.IN) == 2
    assert unit_step(LengthUnit.CM) == 0.5
    assert unit_step(LengthUnit.MM) == 5.0
    assert unit_step(LengthUnit.IN) == 0.1


def test_unit_bounds_converts_min_and_max():
    lo, hi = unit_bounds(2.0, 100.0, LengthUnit.MM)
    assert lo == pytest.approx(20.0)
    assert hi == pytest.approx(1000.0)


def test_format_size_cm():
    assert format_size(15.0, 8.0, LengthUnit.CM) == "15.0 × 8.0 cm"


def test_format_size_mm():
    assert format_size(20.0, 15.0, LengthUnit.MM) == "200 × 150 mm"


def test_format_size_inches():
    assert format_size(20.0, 15.0, LengthUnit.IN) == "7.87 × 5.91 in"


def test_quantize_cm_is_identity_for_cm_and_mm_at_round_values():
    assert quantize_cm(20.0, LengthUnit.CM) == pytest.approx(20.0)
    assert quantize_cm(20.0, LengthUnit.MM) == pytest.approx(20.0)


def test_quantize_cm_reflects_inch_display_rounding():
    # 20cm displays as 7.87in (2 decimals); converting 7.87in back isn't
    # exactly 20cm -- quantize_cm predicts that settled value.
    assert quantize_cm(20.0, LengthUnit.IN) == pytest.approx(7.87 * 2.54)
