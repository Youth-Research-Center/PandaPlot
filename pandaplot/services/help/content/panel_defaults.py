"""Default values and ranges of the sidebar panel controls that the help text states.

Defined once here so the help text and the tests that compare them with the real
panel widgets share the same numbers.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SpinRange:
    """Default value and allowed range of one numeric control."""

    default: float
    minimum: float
    maximum: float


SAVGOL_WINDOW_LENGTH = SpinRange(default=11, minimum=3, maximum=101)
SAVGOL_POLYNOMIAL_ORDER = SpinRange(default=3, minimum=1, maximum=10)

ROLLING_WINDOW_DATASET = SpinRange(default=5, minimum=2, maximum=50)
ROLLING_WINDOW_CHART = SpinRange(default=5, minimum=2, maximum=100)

INTERPOLATION_POINTS_DATASET = SpinRange(default=100, minimum=10, maximum=10000)
INTERPOLATION_POINTS_CHART = SpinRange(default=200, minimum=10, maximum=100000)

FIT_POINTS = SpinRange(default=500, minimum=50, maximum=5000)
DESCRIPTIVE_SIGNIFICANT_DIGITS = SpinRange(default=6, minimum=1, maximum=12)
SIGNIFICANCE_ALPHA = SpinRange(default=0.05, minimum=0.0001, maximum=0.5)
EXPECTED_MEAN = SpinRange(default=0, minimum=-1e12, maximum=1e12)

SAMPLING_RATE_DATASET = SpinRange(default=1000, minimum=0.001, maximum=1e9)
SIGNAL_OVERLAP = SpinRange(default=0.5, minimum=0.0, maximum=0.99)
PEAK_MINIMUM_DISTANCE = SpinRange(default=1, minimum=1, maximum=1_000_000)
PEAK_MINIMUM_HEIGHT_DEFAULT = 0
PEAK_PROMINENCE_DEFAULT = 0
PEAK_THRESHOLD_DEFAULT = 0
