"""Tests for FitService.perform_fit's optional x_min/x_max plotting range."""

import numpy as np

from pandaplot.services.fit.fit_service import FitService


def _linear_data():
    x_data = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    y_data = 2.0 * x_data + 1.0
    return x_data, y_data


def test_perform_fit_defaults_to_data_min_max_when_range_not_given():
    service = FitService()
    x_data, y_data = _linear_data()

    result = service.perform_fit("Linear", x_data, y_data, fit_points=10)

    assert result is not None
    assert result.x_fit.min() == x_data.min()
    assert result.x_fit.max() == x_data.max()


def test_perform_fit_extrapolates_beyond_data_range_when_x_min_x_max_given():
    service = FitService()
    x_data, y_data = _linear_data()

    result = service.perform_fit(
        "Linear", x_data, y_data, fit_points=10, x_min=-5.0, x_max=10.0
    )

    assert result is not None
    assert result.x_fit.min() == -5.0
    assert result.x_fit.max() == 10.0
    assert len(result.x_fit) == 10


def test_perform_fit_custom_range_does_not_change_fitted_parameters():
    service = FitService()
    x_data, y_data = _linear_data()

    default_result = service.perform_fit("Linear", x_data, y_data, fit_points=10)
    ranged_result = service.perform_fit(
        "Linear", x_data, y_data, fit_points=10, x_min=-5.0, x_max=10.0
    )

    assert default_result is not None
    assert ranged_result is not None
    np.testing.assert_allclose(default_result.parameters, ranged_result.parameters)
    assert default_result.params == ranged_result.params
