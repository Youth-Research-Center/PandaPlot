"""Tests for the AnalysisEngine mathematical operations."""

import numpy as np
import pandas as pd
import pytest

from pandaplot.analysis.analysis_engine import AnalysisEngine
from pandaplot.analysis.analysis_types import AnalysisType, AnalysisResult


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _linear_data(n=50):
    """y = 2x + 1  →  derivative = 2, integral ≈ x² + x."""
    x = pd.Series(np.linspace(0, 10, n), name='x')
    y = pd.Series(2 * x + 1, name='y')
    return x, y


def _quadratic_data(n=50):
    """y = x²  →  derivative = 2x, integral ≈ x³/3."""
    x = pd.Series(np.linspace(0, 5, n), name='x')
    y = pd.Series(x ** 2, name='y')
    return x, y


def _sine_data(n=100):
    """y = sin(x)  →  derivative = cos(x)."""
    x = pd.Series(np.linspace(0, 2 * np.pi, n), name='x')
    y = pd.Series(np.sin(x), name='y')
    return x, y


def _noisy_data(n=100, noise_level=0.5):
    """Linear data with Gaussian noise for smoothing tests."""
    rng = np.random.RandomState(42)
    x = pd.Series(np.linspace(0, 10, n), name='x')
    y = pd.Series(2 * x + rng.normal(0, noise_level, n), name='y')
    return x, y


# ===========================================================================
# Derivative
# ===========================================================================

class TestCalculateDerivative:

    def test_central_on_linear_data(self):
        x, y = _linear_data()
        result = AnalysisEngine.calculate_derivative(x, y, method='central')

        assert isinstance(result, AnalysisResult)
        assert result.analysis_type == AnalysisType.DERIVATIVE
        np.testing.assert_allclose(result.result_data.values, 2.0, atol=1e-10)

    def test_forward_on_linear_data(self):
        x, y = _linear_data()
        result = AnalysisEngine.calculate_derivative(x, y, method='forward')

        np.testing.assert_allclose(result.result_data.values, 2.0, atol=1e-10)

    def test_backward_on_linear_data(self):
        x, y = _linear_data()
        result = AnalysisEngine.calculate_derivative(x, y, method='backward')

        np.testing.assert_allclose(result.result_data.values, 2.0, atol=1e-10)

    def test_central_on_quadratic(self):
        x, y = _quadratic_data(n=200)
        result = AnalysisEngine.calculate_derivative(x, y, method='central')

        expected = 2 * x.values  # dy/dx = 2x
        np.testing.assert_allclose(result.result_data.values, expected, atol=0.05)

    def test_result_length_matches_input(self):
        x, y = _linear_data(n=20)
        result = AnalysisEngine.calculate_derivative(x, y, method='central')

        assert len(result.result_data) == len(x)

    def test_forward_result_length(self):
        x, y = _linear_data(n=20)
        result = AnalysisEngine.calculate_derivative(x, y, method='forward')

        assert len(result.result_data) == len(x)

    def test_backward_result_length(self):
        x, y = _linear_data(n=20)
        result = AnalysisEngine.calculate_derivative(x, y, method='backward')

        assert len(result.result_data) == len(x)

    def test_statistics_populated(self):
        x, y = _quadratic_data()
        result = AnalysisEngine.calculate_derivative(x, y)

        assert 'min' in result.statistics
        assert 'max' in result.statistics
        assert 'mean' in result.statistics
        assert 'std' in result.statistics

    def test_subrange(self):
        x, y = _linear_data(n=50)
        result = AnalysisEngine.calculate_derivative(x, y, start_index=10, end_index=30)

        assert len(result.result_data) == 20
        np.testing.assert_allclose(result.result_data.values, 2.0, atol=1e-10)

    def test_source_columns_recorded(self):
        x, y = _linear_data()
        result = AnalysisEngine.calculate_derivative(x, y)

        assert result.source_columns == ['y']


# ===========================================================================
# Integral
# ===========================================================================

class TestCalculateIntegral:

    def test_linear_integral(self):
        """∫(2x + 1)dx from 0 to 10 = x² + x = 110."""
        x, y = _linear_data(n=500)
        result = AnalysisEngine.calculate_integral(x, y)

        assert isinstance(result, AnalysisResult)
        assert result.analysis_type == AnalysisType.INTEGRAL
        assert result.statistics['total_integral'] == pytest.approx(110.0, rel=0.01)

    def test_integral_starts_at_zero(self):
        x, y = _linear_data()
        result = AnalysisEngine.calculate_integral(x, y)

        assert result.result_data.iloc[0] == pytest.approx(0.0, abs=1e-10)

    def test_integral_monotonically_increasing_for_positive_data(self):
        x, y = _linear_data()  # y > 0 everywhere
        result = AnalysisEngine.calculate_integral(x, y)

        diffs = np.diff(result.result_data.values)
        assert np.all(diffs >= 0)

    def test_result_length(self):
        x, y = _linear_data(n=30)
        result = AnalysisEngine.calculate_integral(x, y)

        assert len(result.result_data) == 30

    def test_statistics_populated(self):
        x, y = _linear_data()
        result = AnalysisEngine.calculate_integral(x, y)

        assert 'total_integral' in result.statistics
        assert 'final_value' in result.statistics
        assert 'mean_rate' in result.statistics

    def test_subrange(self):
        x, y = _linear_data(n=100)
        result = AnalysisEngine.calculate_integral(x, y, start_index=0, end_index=50)

        assert len(result.result_data) == 50


# ===========================================================================
# Arc Length
# ===========================================================================

class TestCalculateArcLength:

    def test_straight_horizontal_line(self):
        """Arc length of y=0 from x=0 to x=10 is exactly 10."""
        x = pd.Series(np.linspace(0, 10, 100), name='x')
        y = pd.Series(np.zeros(100), name='y')

        result = AnalysisEngine.calculate_arc_length(x, y)

        assert result.analysis_type == AnalysisType.ARC_LENGTH
        assert result.statistics['total_length'] == pytest.approx(10.0, rel=1e-6)

    def test_straight_diagonal_line(self):
        """Arc length of y=x from 0 to 1 is √2."""
        x = pd.Series(np.linspace(0, 1, 1000), name='x')
        y = pd.Series(x.values, name='y')

        result = AnalysisEngine.calculate_arc_length(x, y)
        assert result.statistics['total_length'] == pytest.approx(np.sqrt(2), rel=1e-4)

    def test_starts_at_zero(self):
        x, y = _linear_data()
        result = AnalysisEngine.calculate_arc_length(x, y)

        assert result.result_data.iloc[0] == pytest.approx(0.0, abs=1e-10)

    def test_monotonically_increasing(self):
        x, y = _linear_data()
        result = AnalysisEngine.calculate_arc_length(x, y)

        diffs = np.diff(result.result_data.values)
        assert np.all(diffs >= 0)

    def test_result_length(self):
        x, y = _linear_data(n=25)
        result = AnalysisEngine.calculate_arc_length(x, y)

        assert len(result.result_data) == 25

    def test_statistics_populated(self):
        x, y = _linear_data()
        result = AnalysisEngine.calculate_arc_length(x, y)

        assert 'total_length' in result.statistics
        assert 'mean_segment' in result.statistics
        assert 'max_segment' in result.statistics


# ===========================================================================
# Smoothing
# ===========================================================================

class TestSmoothData:

    def test_savgol_reduces_noise(self):
        x, y = _noisy_data()
        result = AnalysisEngine.smooth_data(x, y, method='savgol')

        assert result.analysis_type == AnalysisType.SMOOTHING
        assert result.statistics['noise_reduction_percent'] > 0

    def test_rolling_mean_reduces_noise(self):
        x, y = _noisy_data()
        result = AnalysisEngine.smooth_data(x, y, method='rolling_mean')

        assert result.statistics['smoothed_std'] < result.statistics['original_std']

    def test_smoothed_preserves_trend(self):
        """Smoothed data should preserve the underlying linear trend."""
        x, y = _noisy_data(n=200, noise_level=0.3)
        result = AnalysisEngine.smooth_data(x, y, method='savgol')

        # Check correlation with original is high
        assert result.statistics['correlation'] > 0.95

    def test_result_length_matches(self):
        x, y = _noisy_data(n=50)
        result = AnalysisEngine.smooth_data(x, y, method='savgol')

        assert len(result.result_data) == 50

    def test_savgol_custom_window(self):
        x, y = _noisy_data(n=100)
        result = AnalysisEngine.smooth_data(x, y, method='savgol', window_length=21)

        assert len(result.result_data) == 100

    def test_already_smooth_data(self):
        """Smoothing perfectly smooth data should change it minimally."""
        x, y = _linear_data(n=100)
        result = AnalysisEngine.smooth_data(x, y, method='savgol')

        np.testing.assert_allclose(result.result_data.values, y.values, atol=0.1)


# ===========================================================================
# Interpolation
# ===========================================================================

class TestInterpolateData:

    def test_linear_interpolation(self):
        x, y = _linear_data(n=10)
        result = AnalysisEngine.interpolate_data(x, y, method='linear', num_points=50)

        assert result.analysis_type == AnalysisType.INTERPOLATION
        assert len(result.result_data) == 50

    def test_cubic_interpolation(self):
        x, y = _quadratic_data(n=20)
        result = AnalysisEngine.interpolate_data(x, y, method='cubic', num_points=100)

        assert len(result.result_data) == 100

    def test_interpolation_matches_at_endpoints(self):
        x, y = _linear_data(n=10)
        result = AnalysisEngine.interpolate_data(x, y, method='linear', num_points=50)

        # First and last interpolated values should match original endpoints
        assert result.result_data.iloc[0] == pytest.approx(y.iloc[0], abs=0.01)
        assert result.result_data.iloc[-1] == pytest.approx(y.iloc[-1], abs=0.01)

    def test_linear_interpolation_accuracy(self):
        """Interpolating linear data should perfectly reconstruct it."""
        x, y = _linear_data(n=5)
        result = AnalysisEngine.interpolate_data(x, y, method='linear', num_points=50)

        expected = 2 * result.x_data + 1
        np.testing.assert_allclose(result.result_data.values, expected.values, atol=1e-10)

    def test_default_num_points(self):
        x, y = _linear_data(n=20)
        result = AnalysisEngine.interpolate_data(x, y, method='linear')

        assert len(result.result_data) == 40  # 2x input length

    def test_small_dataset_cubic_fallback(self):
        """Cubic with < 4 points should fallback to linear without error."""
        x = pd.Series([1.0, 2.0, 3.0], name='x')
        y = pd.Series([1.0, 4.0, 9.0], name='y')

        result = AnalysisEngine.interpolate_data(x, y, method='cubic', num_points=10)

        assert len(result.result_data) == 10

    def test_statistics_populated(self):
        x, y = _linear_data(n=10)
        result = AnalysisEngine.interpolate_data(x, y, num_points=30)

        assert result.statistics['original_points'] == 10
        assert result.statistics['interpolated_points'] == 30
        assert result.statistics['point_density_ratio'] == pytest.approx(3.0)

    def test_nearest_interpolation(self):
        x = pd.Series([0.0, 1.0, 2.0, 3.0], name='x')
        y = pd.Series([0.0, 10.0, 20.0, 30.0], name='y')

        result = AnalysisEngine.interpolate_data(x, y, method='nearest', num_points=7)

        assert len(result.result_data) == 7


# ===========================================================================
# AnalysisResult helpers
# ===========================================================================

class TestAnalysisResult:

    def test_to_dataframe(self):
        x, y = _linear_data(n=10)
        result = AnalysisEngine.calculate_derivative(x, y)

        df = result.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert 'x' in df.columns
        assert 'result' in df.columns
        assert len(df) == 10

    def test_get_column_name(self):
        x, y = _linear_data()
        result = AnalysisEngine.calculate_derivative(x, y)

        assert result.get_column_name() == 'y_derivative'

    def test_get_column_name_integral(self):
        x, y = _linear_data()
        result = AnalysisEngine.calculate_integral(x, y)

        assert result.get_column_name() == 'y_integral'
