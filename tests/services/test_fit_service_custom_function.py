"""Tests for FitService custom-function parsing."""

import numpy as np
import pytest

from pandaplot.services.fit.fit_service import FitService


def test_custom_function_with_arcsin_is_not_mangled_into_arcnp_sin():
    service = FitService()

    func, params = service._create_custom_function("a*arcsin(x)+b", "a, b", None)

    x = np.linspace(-0.9, 0.9, 7)
    assert params == ["a", "b"]
    np.testing.assert_allclose(func(x, 2.0, 0.5), 2.0 * np.arcsin(x) + 0.5)


def test_custom_fit_with_arcsin_recovers_parameters():
    service = FitService()
    x_data = np.linspace(-0.9, 0.9, 20)
    y_data = 3.0 * np.arcsin(x_data) - 1.0

    result = service.perform_fit(
        "Custom Function",
        x_data,
        y_data,
        fit_points=10,
        custom_function="a*arcsin(x)+b",
        custom_parameters="a, b",
    )

    assert result is not None
    assert result.params["a"] == pytest.approx(3.0)
    assert result.params["b"] == pytest.approx(-1.0)


def test_custom_function_keeps_explicit_np_prefix():
    service = FitService()

    func, _params = service._create_custom_function("a*np.sin(x)", "a", None)

    x = np.linspace(0.0, 3.0, 5)
    np.testing.assert_allclose(func(x, 2.0), 2.0 * np.sin(x))


@pytest.mark.parametrize(
    ("expression", "reference"),
    [
        ("a*arctan(x)", lambda x, a: a * np.arctan(x)),
        ("a*tanh(x)", lambda x, a: a * np.tanh(x)),
        ("a*sinh(x)+cosh(x)", lambda x, a: a * np.sinh(x) + np.cosh(x)),
        ("a*log10(x)", lambda x, a: a * np.log10(x)),
        ("a*log2(x)", lambda x, a: a * np.log2(x)),
        ("a*abs(x-1)", lambda x, a: a * np.abs(x - 1)),
        ("a*arctan2(x, 2)", lambda x, a: a * np.arctan2(x, 2)),
        ("a*sqrt(x)+exp(-x)", lambda x, a: a * np.sqrt(x) + np.exp(-x)),
        ("a*np.tanh(x)", lambda x, a: a * np.tanh(x)),
    ],
)
def test_custom_function_accepts_bare_numpy_function_names(expression, reference):
    service = FitService()

    func, _params = service._create_custom_function(expression, "a", None)

    x = np.linspace(0.5, 3.0, 6)
    np.testing.assert_allclose(func(x, 1.5), reference(x, 1.5))


def test_custom_function_parameter_takes_precedence_over_function_name():
    service = FitService()

    func, _params = service._create_custom_function("exp*x", "exp", None)

    x = np.linspace(0.0, 1.0, 4)
    np.testing.assert_allclose(func(x, 3.0), 3.0 * x)
