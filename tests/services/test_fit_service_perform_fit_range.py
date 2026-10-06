"""Tests for FitService.perform_fit's optional x_min/x_max plotting range."""

import numpy as np
import pytest

from pandaplot.services.fit.fit_service import FIT_CATEGORIES, FitService


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


def test_fit_categories_cover_every_fit_model_once():
    categorized_fits = [
        fit_name
        for fit_names in FIT_CATEGORIES.values()
        for fit_name in fit_names
    ]

    assert len(categorized_fits) == len(set(categorized_fits))
    assert set(categorized_fits) == {
        "Linear",
        "Quadratic",
        "Cubic",
        "Quartic",
        "Quintic",
        "Exponential",
        "Exponential Decay",
        "Exponential Growth to Maximum",
        "Logistic Sigmoid",
        "Gaussian Peak",
        "Power",
        "Logarithmic",
        "Custom Function",
    }


@pytest.mark.parametrize(
    ("fit_type", "x_data", "y_function"),
    [
        (
            "Cubic",
            np.linspace(-2.0, 3.0, 80),
            lambda x: 0.2 * x**3 - x**2 + 3 * x + 1,
        ),
        (
            "Exponential Decay",
            np.linspace(0.0, 5.0, 80),
            lambda x: 4 * np.exp(-0.7 * x) + 1,
        ),
        (
            "Exponential Growth to Maximum",
            np.linspace(0.0, 5.0, 80),
            lambda x: 6 * (1 - np.exp(-0.8 * x)) + 2,
        ),
        (
            "Logistic Sigmoid",
            np.linspace(-8.0, 8.0, 100),
            lambda x: 8 / (1 + np.exp(-1.2 * (x - 1))) + 2,
        ),
        (
            "Gaussian Peak",
            np.linspace(-5.0, 5.0, 100),
            lambda x: 5 * np.exp(-0.5 * ((x - 0.7) / 0.8) ** 2) + 0.5,
        ),
    ],
)
def test_new_fit_models_recover_synthetic_curves(fit_type, x_data, y_function):
    pytest.importorskip("scipy")
    service = FitService()
    y_data = y_function(x_data)

    result = service.perform_fit(fit_type, x_data, y_data, fit_points=100)

    assert result is not None
    np.testing.assert_allclose(result.y_fit, y_function(result.x_fit), rtol=0.02, atol=0.02)


def test_polynomial_fit_requires_enough_points_for_its_coefficients():
    service = FitService()
    x_data = np.array([0.0, 1.0, 2.0])
    y_data = x_data**3

    with pytest.raises(ValueError, match="At least 4 data points"):
        service.perform_fit("Cubic", x_data, y_data)
