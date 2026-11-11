"""Tests for AnalysisEngine.calculate_derivative (#291).

A single-point (or empty) slice fed to any derivative method used to crash
with an opaque IndexError: np.diff()/np.gradient() on fewer than 2 points
return/operate on an empty array, and indexing into that (derivative[-1]/
derivative[0]) is what actually raised.
"""
import pandas as pd
import pytest

from pandaplot.analysis.analysis_engine import AnalysisEngine


@pytest.mark.parametrize("method", ["central", "forward", "backward"])
def test_single_point_slice_raises_a_clear_validation_error(method):
    x = pd.Series([1.0])
    y = pd.Series([2.0])

    with pytest.raises(ValueError, match="at least 2 data points"):
        AnalysisEngine.calculate_derivative(x, y, method=method)


@pytest.mark.parametrize("method", ["central", "forward", "backward"])
def test_empty_slice_raises_a_clear_validation_error(method):
    x = pd.Series([], dtype=float)
    y = pd.Series([], dtype=float)

    with pytest.raises(ValueError, match="at least 2 data points"):
        AnalysisEngine.calculate_derivative(x, y, method=method)


@pytest.mark.parametrize("method", ["central", "forward", "backward"])
def test_two_point_slice_still_computes_successfully(method):
    """The fix must only reject slices too short to differentiate -- the
    smallest valid slice (2 points) should keep working."""
    x = pd.Series([1.0, 2.0])
    y = pd.Series([2.0, 4.0])

    result = AnalysisEngine.calculate_derivative(x, y, method=method)

    assert len(result.result_data) == 2
    assert list(result.result_data) == [2.0, 2.0]


def test_start_and_end_index_slicing_down_to_one_point_also_raises():
    """Regression: the same crash was reachable via start_index/end_index
    slicing a longer series down to a single row, not just a naturally
    short input."""
    x = pd.Series([1.0, 2.0, 3.0, 4.0])
    y = pd.Series([1.0, 4.0, 9.0, 16.0])

    with pytest.raises(ValueError, match="at least 2 data points"):
        AnalysisEngine.calculate_derivative(x, y, method="forward", start_index=1, end_index=2)


def test_savgol_default_window_fits_even_length_slice():
    """Regression: the default Savitzky-Golay window for an even-length slice
    (n=10) was n+1, which exceeds the data length and made savgol_filter raise."""
    x = pd.Series([float(i) for i in range(10)], name="x")
    y = pd.Series([float(i) ** 2 for i in range(10)], name="y")

    result = AnalysisEngine.smooth_data(x, y, method="savgol")

    assert len(result.result_data) == 10
