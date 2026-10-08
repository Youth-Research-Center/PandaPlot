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
        "Lorentzian Peak",
        "Sine",
        "Damped Sine",
        "Cosine",
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
        (
            "Lorentzian Peak",
            np.linspace(-6.0, 6.0, 150),
            lambda x: 4 / (1 + ((x - 0.5) / 0.9) ** 2) + 0.3,
        ),
        (
            "Damped Sine",
            np.linspace(0.0, 10.0, 300),
            lambda x: 5 * np.exp(-0.3 * x) * np.sin(2.1 * x + 0.4) + 1,
        ),
        (
            "Sine",
            np.linspace(0.0, 10.0, 200),
            lambda x: 3 * np.sin(1.7 * x + 0.6) + 1,
        ),
        (
            "Cosine",
            np.linspace(0.0, 10.0, 200),
            lambda x: 2.5 * np.cos(2.3 * x - 1.1) - 0.5,
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


@pytest.mark.parametrize(
    ("fit_type", "y_function"),
    [
        ("Exponential Decay", lambda x: 4 * np.exp(-0.001 * x) + 1),
        ("Exponential Growth to Maximum", lambda x: 4 * (1 - np.exp(-0.001 * x)) + 1),
    ],
)
def test_translated_x_exponential_fits_recover_parameters(fit_type, y_function):
    pytest.importorskip("scipy")
    x_data = np.linspace(1000.0, 1005.0, 80)
    y_data = y_function(x_data)

    result = FitService().perform_fit(fit_type, x_data, y_data, fit_points=100)

    assert result is not None
    assert result.params["b"] == pytest.approx(0.001, rel=0.02)
    np.testing.assert_allclose(result.y_fit, y_function(result.x_fit), rtol=1e-8, atol=1e-8)


def test_power_and_logarithmic_fits_share_a_category():
    assert FIT_CATEGORIES["Power & Logarithmic"] == ("Power", "Logarithmic")
    assert "Other" not in FIT_CATEGORIES
    assert FIT_CATEGORIES["Periodic"] == ("Sine", "Cosine", "Damped Sine")


def test_fixed_polynomial_coefficient_is_applied_to_the_fitted_curve():
    pytest.importorskip("scipy")
    x_data = np.linspace(-3.0, 3.0, 60)
    y_data = 1.0 * x_data**3 - 2.0 * x_data**2 + 0.5 * x_data + 4.0

    result = FitService().perform_fit("Cubic", x_data, y_data, fit_points=50, fixed_parameters="a=1")

    assert result is not None
    assert result.params["a"] == 1.0
    reported = np.polyval([result.params[name] for name in ("a", "b", "c", "d")], result.x_fit)
    np.testing.assert_allclose(result.y_fit, reported, rtol=1e-8, atol=1e-8)
    np.testing.assert_allclose(result.y_fit, np.polyval([1.0, -2.0, 0.5, 4.0], result.x_fit), rtol=1e-6, atol=1e-6)


def test_damped_sine_without_visible_decay_fits_translated_x_data():
    pytest.importorskip("scipy")
    x_data = np.linspace(1000.0, 1001.0, 6)
    y_data = np.sin(2 * np.pi * (x_data - 1000.0) + np.pi / 4) + 1

    result = FitService().perform_fit("Damped Sine", x_data, y_data, fit_points=20)

    assert result is not None
    assert np.all(np.isfinite(result.y_fit))


@pytest.mark.parametrize(
    ("fit_type", "fixed_parameters"),
    [
        ("Exponential Decay", "b=-1"),
        ("Exponential Growth to Maximum", "b=-0.5"),
        ("Gaussian Peak", "sigma=0"),
        ("Lorentzian Peak", "gamma=-2"),
        ("Damped Sine", "k=-0.1"),
    ],
)
def test_fixed_parameter_outside_model_bounds_is_rejected(fit_type, fixed_parameters):
    x_data = np.linspace(0.0, 5.0, 40)
    y_data = np.exp(-x_data)

    with pytest.raises(ValueError, match="must be within"):
        FitService().perform_fit(fit_type, x_data, y_data, fixed_parameters=fixed_parameters)
