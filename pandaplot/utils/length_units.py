"""Conversion helpers for the app's configurable chart-size measurement unit
(cm / mm / in).

Internal storage of chart width/height is always centimeters (see
``ChartDisplayConfig.default_width_cm``/``default_height_cm`` and
``Chart.config["width_cm"/"height_cm"]``); these helpers convert only at the
UI boundaries that display those values in the user's chosen unit.
"""
from __future__ import annotations

from pandaplot.models.state.config import LengthUnit

_CM_PER_UNIT: dict[LengthUnit, float] = {
    LengthUnit.CM: 1.0,
    LengthUnit.MM: 0.1,
    LengthUnit.IN: 2.54,
}

_DECIMALS: dict[LengthUnit, int] = {LengthUnit.CM: 1, LengthUnit.MM: 0, LengthUnit.IN: 2}
_STEP: dict[LengthUnit, float] = {LengthUnit.CM: 0.5, LengthUnit.MM: 5.0, LengthUnit.IN: 0.1}
_SUFFIX: dict[LengthUnit, str] = {LengthUnit.CM: " cm", LengthUnit.MM: " mm", LengthUnit.IN: " in"}


def to_cm(value: float, unit: LengthUnit) -> float:
    """Convert a value expressed in `unit` to centimeters."""
    return value * _CM_PER_UNIT[unit]


def from_cm(value_cm: float, unit: LengthUnit) -> float:
    """Convert a centimeter value to `unit`."""
    return value_cm / _CM_PER_UNIT[unit]


def unit_suffix(unit: LengthUnit) -> str:
    return _SUFFIX[unit]


def unit_decimals(unit: LengthUnit) -> int:
    return _DECIMALS[unit]


def unit_step(unit: LengthUnit) -> float:
    return _STEP[unit]


def unit_bounds(min_cm: float, max_cm: float, unit: LengthUnit) -> tuple[float, float]:
    """Convert a (min, max) centimeter range into `unit`, for spin box ranges."""
    return from_cm(min_cm, unit), from_cm(max_cm, unit)


def format_size(width_cm: float, height_cm: float, unit: LengthUnit) -> str:
    """Format a (width_cm, height_cm) pair as a display string in `unit`,
    e.g. "200 × 150 mm"."""
    decimals = _DECIMALS[unit]
    width = from_cm(width_cm, unit)
    height = from_cm(height_cm, unit)
    return f"{width:.{decimals}f} × {height:.{decimals}f}{_SUFFIX[unit]}"


def quantize_cm(value_cm: float, unit: LengthUnit) -> float:
    """Round `value_cm` to the precision `unit` displays with, then convert
    back to centimeters -- i.e. predict the centimeter value a spin box
    would settle on after showing `value_cm` in `unit`. Used to compare a
    freshly-loaded value against a round-tripped one without the comparison
    being tripped up by unit-rounding alone."""
    return to_cm(round(from_cm(value_cm, unit), _DECIMALS[unit]), unit)


__all__ = [
    "to_cm",
    "from_cm",
    "unit_suffix",
    "unit_decimals",
    "unit_step",
    "unit_bounds",
    "format_size",
    "quantize_cm",
]
