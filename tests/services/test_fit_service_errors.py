"""FitService turns scipy's raw fit failures into messages written for the user."""
from unittest.mock import Mock

import numpy as np
import pytest
import scipy.optimize

from pandaplot.services.fit.fit_service import CUSTOM_FUNCTION_FIT, FitService
from pandaplot.utils.error_messages import describe_error
from pandaplot.utils.errors import UserFacingError

X = np.linspace(0.0, 5.0, 20)
Y = 2.0 * X + 1.0


def _fit(fit_type: str = "Linear", x: np.ndarray = X, y: np.ndarray = Y, **kwargs):
    return FitService().perform_fit(fit_type=fit_type, x_data=x, y_data=y, **kwargs)


def test_non_convergence_becomes_a_plain_user_facing_message(monkeypatch):
    raw = RuntimeError("Optimal parameters not found: Number of calls to function has reached maxfev = 800.")
    monkeypatch.setattr(scipy.optimize, "curve_fit", Mock(side_effect=raw))

    with pytest.raises(UserFacingError) as info:
        _fit()

    assert str(info.value) == "The fit did not converge for this data. Try another model or a narrower X range."
    assert info.value.__cause__ is raw


def test_custom_fit_non_convergence_mentions_starting_values(monkeypatch):
    monkeypatch.setattr(scipy.optimize, "curve_fit", Mock(side_effect=RuntimeError("Optimal parameters not found: maxfev")))

    with pytest.raises(UserFacingError, match="Try other starting values"):
        _fit(CUSTOM_FUNCTION_FIT, custom_function="a*x + b", custom_parameters="a, b")


def test_other_runtime_errors_keep_their_type(monkeypatch):
    monkeypatch.setattr(scipy.optimize, "curve_fit", Mock(side_effect=RecursionError("maximum recursion depth exceeded")))

    with pytest.raises(RecursionError) as info:
        _fit()

    assert describe_error(info.value).reason == "Something went wrong that PandaPlot did not expect."


def test_nan_or_inf_data_is_rejected_with_a_plain_message():
    y = Y.copy()
    y[3] = np.nan

    with pytest.raises(UserFacingError, match="empty or infinite values"):
        _fit(y=y)
