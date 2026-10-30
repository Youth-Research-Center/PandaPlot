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
