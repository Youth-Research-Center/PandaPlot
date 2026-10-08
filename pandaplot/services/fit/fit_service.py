import logging
import re
from dataclasses import dataclass

import numpy as np

MIN_FIT_POINTS = 2
_MAX_EXP_ARGUMENT = 700


def _polynomial(x: np.ndarray, *coefficients: float) -> np.ndarray:
    return np.polyval(coefficients, x)


def _sigmoid(x: np.ndarray, amplitude: float, slope: float, midpoint: float, offset: float) -> np.ndarray:
    exponent = np.clip(-slope * (x - midpoint), -700, 700)
    return amplitude / (1 + np.exp(exponent)) + offset


def _gaussian_peak(x: np.ndarray, amplitude: float, center: float, width: float, offset: float) -> np.ndarray:
    return amplitude * np.exp(-0.5 * ((x - center) / width) ** 2) + offset


def _exponential_decay(x: np.ndarray, amplitude: float, rate: float, offset: float) -> np.ndarray:
    return amplitude * np.exp(np.clip(-rate * x, -700, 700)) + offset


def _exponential_growth_to_maximum(x: np.ndarray, amplitude: float, rate: float, offset: float) -> np.ndarray:
    return amplitude * (1 - np.exp(np.clip(-rate * x, -700, 700))) + offset


def _sine(x: np.ndarray, amplitude: float, frequency: float, phase: float, offset: float) -> np.ndarray:
    return amplitude * np.sin(frequency * x + phase) + offset


def _cosine(x: np.ndarray, amplitude: float, frequency: float, phase: float, offset: float) -> np.ndarray:
    return amplitude * np.cos(frequency * x + phase) + offset


def _lorentzian_peak(x: np.ndarray, amplitude: float, center: float, width: float, offset: float) -> np.ndarray:
    return amplitude / (1 + ((x - center) / width) ** 2) + offset


def _damped_sine(
    x: np.ndarray, amplitude: float, decay: float, frequency: float, phase: float, offset: float,
) -> np.ndarray:
    return amplitude * np.exp(np.clip(-decay * x, -700, 700)) * np.sin(frequency * x + phase) + offset


def _periodic_initial_guess(x: np.ndarray, y: np.ndarray, *, cosine: bool) -> list[float]:
    """Estimate amplitude, angular frequency, phase and offset of a sinusoid.

    The frequency comes from the strongest non-DC FFT bin of the data resampled
    onto a uniform grid; amplitude, phase and offset then follow from a linear
    least-squares fit at that frequency.

    Args:
        x: Independent variable values.
        y: Dependent variable values.
        cosine: Report the phase for a cosine model instead of a sine model.

    Returns:
        Initial ``[amplitude, frequency, phase, offset]``.
    """
    order = np.argsort(x)
    sorted_x = x[order]
    sorted_y = y[order]
    x_span = max(float(np.ptp(sorted_x)), np.finfo(float).eps)

    grid = np.linspace(sorted_x[0], sorted_x[-1], len(sorted_x))
    resampled = np.interp(grid, sorted_x, sorted_y)
    spectrum = np.abs(np.fft.rfft(resampled - resampled.mean()))
    peak_bin = int(np.argmax(spectrum[1:])) + 1 if len(spectrum) > 1 else 1
    frequency = 2 * np.pi * peak_bin / x_span

    design = np.column_stack([np.sin(frequency * sorted_x), np.cos(frequency * sorted_x), np.ones_like(sorted_x)])
    (sin_coefficient, cos_coefficient, offset), *_ = np.linalg.lstsq(design, sorted_y, rcond=None)
    amplitude = float(np.hypot(sin_coefficient, cos_coefficient))
    if cosine:
        phase = float(np.arctan2(-sin_coefficient, cos_coefficient))
    else:
        phase = float(np.arctan2(cos_coefficient, sin_coefficient))
    return [amplitude, float(frequency), phase, float(offset)]


def _polynomial_initial_guess(x: np.ndarray, y: np.ndarray, *, degree: int) -> list[float]:
    coefficients = np.polyfit(x, y, degree)
    return coefficients.tolist()


def _peak_initial_guess(x: np.ndarray, y: np.ndarray) -> list[float]:
    peak_index = int(np.argmax(y))
    width = max(float(np.ptp(x)) / 6, np.finfo(float).eps)
    return [float(y.max() - y.min()), float(x[peak_index]), width, float(y.min())]


def _sigmoid_initial_guess(x: np.ndarray, y: np.ndarray) -> list[float]:
    order = np.argsort(x)
    sorted_x = x[order]
    sorted_y = y[order]
    tail_count = max(1, len(sorted_y) // 10)
    start_level = float(np.mean(sorted_y[:tail_count]))
    end_level = float(np.mean(sorted_y[-tail_count:]))
    amplitude = end_level - start_level

    if abs(amplitude) <= np.finfo(float).eps:
        x_range = max(float(np.ptp(sorted_x)), np.finfo(float).eps)
        return [float(np.ptp(sorted_y)), 4 / x_range, float(np.median(sorted_x)), float(sorted_y.min())]

    fractions = (sorted_y - start_level) / amplitude
    central_points = (fractions > 0.05) & (fractions < 0.95)
    if np.count_nonzero(central_points) < 2:
        midpoint = float(sorted_x[np.argmin(np.abs(fractions - 0.5))])
        slope = 4 / max(float(np.ptp(sorted_x)), np.finfo(float).eps)
    else:
        logits = np.log(fractions[central_points] / (1 - fractions[central_points]))
        slope, intercept = np.polyfit(sorted_x[central_points], logits, 1)
        midpoint = float(-intercept / slope) if abs(slope) > np.finfo(float).eps else float(np.median(sorted_x))

    return [amplitude, float(slope), midpoint, start_level]


def _decay_initial_guess(x: np.ndarray, y: np.ndarray) -> list[float]:
    order = np.argsort(x)
    sorted_x = x[order]
    sorted_y = y[order]
    x_span = max(float(np.ptp(sorted_x)), np.finfo(float).eps)
    rate = 1 / max(x_span, abs(float(sorted_x[0])), np.finfo(float).eps)
    local_amplitude = float(sorted_y[0] - sorted_y[-1]) / -np.expm1(-rate * x_span)
    amplitude = local_amplitude * np.exp(rate * sorted_x[0])
    offset = float(sorted_y[0] - local_amplitude)
    return [amplitude, rate, offset]


def _growth_initial_guess(x: np.ndarray, y: np.ndarray) -> list[float]:
    order = np.argsort(x)
    sorted_x = x[order]
    sorted_y = y[order]
    x_span = max(float(np.ptp(sorted_x)), np.finfo(float).eps)
    rate = 1 / max(x_span, abs(float(sorted_x[0])), np.finfo(float).eps)
    local_amplitude = float(sorted_y[-1] - sorted_y[0]) / -np.expm1(-rate * x_span)
    amplitude = local_amplitude * np.exp(rate * sorted_x[0])
    offset = float(sorted_y[0] - amplitude * -np.expm1(-rate * sorted_x[0]))
    return [amplitude, rate, offset]


def _damped_sine_initial_guess(x: np.ndarray, y: np.ndarray) -> list[float]:
    amplitude, frequency, phase, offset = _periodic_initial_guess(x, y, cosine=False)
    order = np.argsort(x)
    sorted_x = x[order]
    residual = y[order] - offset
    half = len(sorted_x) // 2
    first_rms = float(np.sqrt(np.mean(residual[:half] ** 2))) if half else 0.0
    second_rms = float(np.sqrt(np.mean(residual[half:] ** 2)))
    spacing = float(np.mean(sorted_x[half:]) - np.mean(sorted_x[:half])) if half else 0.0
    decay = 0.0
    if first_rms > second_rms > 0 and spacing > 0:
        decay = float(np.log(first_rms / second_rms) / spacing)
    if decay * float(np.max(np.abs(sorted_x))) > _MAX_EXP_ARGUMENT:
        decay = 0.0
    return [amplitude * float(np.exp(decay * np.mean(sorted_x))), decay, frequency, phase, offset]


FIT_DEFINITIONS = {
    "Linear": {
        "function": lambda x, a, b: a * x + b,
        "parameters": ["a", "b"],
        "equation": "a*x + b",
        "category": "Polynomial",
        "description": "y = ax + b",
    },
    "Quadratic": {
        "function": lambda x, a, b, c: a * x ** 2 + b * x + c,
        "parameters": ["a", "b", "c"],
        "equation": "a*x**2 + b*x + c",
        "category": "Polynomial",
        "description": "y = ax² + bx + c",
        "initial_guess": lambda x, y: _polynomial_initial_guess(x, y, degree=2),
    },
    "Cubic": {
        "function": _polynomial,
        "parameters": ["a", "b", "c", "d"],
        "equation": "a*x**3 + b*x**2 + c*x + d",
        "category": "Polynomial",
        "description": "polynomial, degree 3",
        "initial_guess": lambda x, y: _polynomial_initial_guess(x, y, degree=3),
    },
    "Quartic": {
        "function": _polynomial,
        "parameters": ["a", "b", "c", "d", "e"],
        "equation": "a*x**4 + b*x**3 + c*x**2 + d*x + e",
        "category": "Polynomial",
        "description": "polynomial, degree 4",
        "initial_guess": lambda x, y: _polynomial_initial_guess(x, y, degree=4),
    },
    "Quintic": {
        "function": _polynomial,
        "parameters": ["a", "b", "c", "d", "e", "f"],
        "equation": "a*x**5 + b*x**4 + c*x**3 + d*x**2 + e*x + f",
        "category": "Polynomial",
        "description": "polynomial, degree 5",
        "initial_guess": lambda x, y: _polynomial_initial_guess(x, y, degree=5),
    },
    "Exponential": {
        "function": lambda x, a, b, c: a * np.exp(b * x) + c,
        "parameters": ["a", "b", "c"],
        "equation": "a*exp(b*x) + c",
        "category": "Exponential",
        "description": "y = ae^(bx) + c",
    },
    "Exponential Decay": {
        "function": _exponential_decay,
        "parameters": ["a", "b", "c"],
        "equation": "a*exp(-b*x) + c",
        "category": "Exponential",
        "description": "y = ae⁻ᵇˣ + c",
        "initial_guess": _decay_initial_guess,
        "bounds": {"b": (0, np.inf)},
    },
    "Exponential Growth to Maximum": {
        "function": _exponential_growth_to_maximum,
        "parameters": ["a", "b", "c"],
        "equation": "a*(1 - exp(-b*x)) + c",
        "category": "Exponential",
        "description": "y = a(1 - e⁻ᵇˣ) + c",
        "initial_guess": _growth_initial_guess,
        "bounds": {"b": (0, np.inf)},
    },
    "Logistic Sigmoid": {
        "function": _sigmoid,
        "parameters": ["a", "b", "x0", "c"],
        "equation": "a/(1 + exp(-b*(x - x0))) + c",
        "category": "Sigmoid",
        "description": "logistic sigmoid",
        "initial_guess": _sigmoid_initial_guess,
    },
    "Gaussian Peak": {
        "function": _gaussian_peak,
        "parameters": ["a", "x0", "sigma", "c"],
        "equation": "a*exp(-0.5*((x - x0)/sigma)**2) + c",
        "category": "Peak",
        "description": "Gaussian peak",
        "initial_guess": _peak_initial_guess,
        "bounds": {"sigma": (np.finfo(float).eps, np.inf)},
    },
    "Lorentzian Peak": {
        "function": _lorentzian_peak,
        "parameters": ["a", "x0", "gamma", "c"],
        "equation": "a/(1 + ((x - x0)/gamma)**2) + c",
        "category": "Peak",
        "description": "Lorentzian peak",
        "initial_guess": _peak_initial_guess,
        "bounds": {"gamma": (np.finfo(float).eps, np.inf)},
    },
    "Sine": {
        "function": _sine,
        "parameters": ["a", "b", "c", "d"],
        "equation": "a*sin(b*x + c) + d",
        "category": "Periodic",
        "description": "y = a·sin(bx + c) + d",
        "initial_guess": lambda x, y: _periodic_initial_guess(x, y, cosine=False),
    },
    "Cosine": {
        "function": _cosine,
        "parameters": ["a", "b", "c", "d"],
        "equation": "a*cos(b*x + c) + d",
        "category": "Periodic",
        "description": "y = a·cos(bx + c) + d",
        "initial_guess": lambda x, y: _periodic_initial_guess(x, y, cosine=True),
    },
    "Damped Sine": {
        "function": _damped_sine,
        "parameters": ["a", "k", "b", "c", "d"],
        "equation": "a*exp(-k*x)*sin(b*x + c) + d",
        "category": "Periodic",
        "description": "y = a·e⁻ᵏˣ·sin(bx + c) + d",
        "initial_guess": _damped_sine_initial_guess,
        "bounds": {"k": (0, np.inf)},
    },
    "Power": {
        "function": lambda x, a, b, c: a * (x ** b) + c,
        "parameters": ["a", "b", "c"],
        "equation": "a*x**b + c",
        "category": "Power & Logarithmic",
        "description": "y = ax^b + c",
    },
    "Logarithmic": {
        "function": lambda x, a, b: a * np.log(x) + b,
        "parameters": ["a", "b"],
        "equation": "a*ln(x) + b",
        "category": "Power & Logarithmic",
        "description": "y = a*ln(x) + b",
    },
}


FIT_CATEGORIES: dict[str, tuple[str, ...]] = {}
for _fit_name, _fit_definition in FIT_DEFINITIONS.items():
    _category = _fit_definition["category"]
    FIT_CATEGORIES[_category] = (*FIT_CATEGORIES.get(_category, ()), _fit_name)
FIT_CATEGORIES["Custom"] = ("Custom Function",)


@dataclass
class FitResult:
    fit_type: str
    parameters: np.ndarray
    errors: np.ndarray
    param_names: list[str]
    params: dict[str, float]
    r_squared: float | None
    x_fit: np.ndarray
    y_fit: np.ndarray
    x_data: np.ndarray
    y_data: np.ndarray
    covariance: np.ndarray
    confidence_lower: np.ndarray | None = None
    confidence_upper: np.ndarray | None = None
    source_dataset_id: str | None = None
    source_x_column: str | None = None
    source_y_column: str | None = None
    source_x_column_id: str | None = None
    source_y_column_id: str | None = None
    sigma_y: np.ndarray | None = None
    equation: str | None = None

class FitService:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.fixed_params = {}

    def _get_fit_name(self, fit_type: str) -> str:
        if fit_type in FIT_DEFINITIONS or fit_type == "Custom Function":
            return fit_type
        return fit_type.split(" (")[0]

    def _get_fit_func(
            self,
            fit_type: str,
            custom_function: str | None = None,
            custom_parameters: str | None = None,
            fixed_parameters: str | None = None,
    ):
        fit_name = self._get_fit_name(fit_type)
        if fit_name == "Custom Function":
            return self._create_custom_function(
                custom_function,
                custom_parameters,
                fixed_parameters,
            )

        fit = FIT_DEFINITIONS.get(fit_name)
        if fit is None:
            self.logger.error("Unknown fit type: %s", fit_type)
            raise ValueError(f"Unknown fit type: {fit_type}")

        return fit["function"], fit["parameters"]


    def _create_custom_function(
            self,
            function_str: str | None,
            params_str: str | None,
            initial_str: str | None,
    ):
        function_str = (function_str or "").strip()
        params_str = (params_str or "").strip()
        initial_str = (initial_str or "").strip()

        if not function_str or not params_str:
            raise ValueError("Custom function and parameters must be specified")

        function_names = ["sin", "cos", "tan", "sqrt", "exp", "log", "arcsin", "arccos"]

        for func in function_names:
            function_str = function_str.replace(
                f"{func}(",
                f"np.{func}("
            )
            function_str = function_str.replace(
                f"np.np.{func}(",
                f"np.{func}("
            )

        params = [p.strip() for p in params_str.split(",")]

        fixed_params = {}
        if initial_str:
            for item in initial_str.split(","):
                if "=" in item:
                    key, val = item.split("=", 1)
                    fixed_params[key.strip()] = float(val)

        free_params = [
            p for p in params
            if p not in fixed_params
        ]

        def custom_func(x, *free_args):
            local_vars = {"x": x, "np": np}

            for key, value in fixed_params.items():
                local_vars[key] = value

            for i, param in enumerate(free_params):
                local_vars[param] = free_args[i]

            return eval(
                function_str,
                {"__builtins__": {}},
                local_vars,
            )

        return custom_func, params

    def perform_fit(
            self,
            fit_type: str,
            x_data: np.ndarray,
            y_data: np.ndarray,
            fit_points: int = 500,
            *,
            calculate_r_squared: bool = True,
            confidence_bands: bool = False,
            sigma_y: np.ndarray | None = None,
            custom_function: str | None = None,
            custom_parameters: str | None = None,
            fixed_parameters: str | None = None,
            x_min: float | None = None,
            x_max: float | None = None,
    ) -> FitResult | None:

        from scipy.optimize import curve_fit

        if len(x_data) < MIN_FIT_POINTS:
            raise ValueError(f"At least {MIN_FIT_POINTS} data points are required for fitting.")

        try:
            fit_func, param_names = self._get_fit_func(
                fit_type,
                custom_function=custom_function,
                custom_parameters=custom_parameters,
                fixed_parameters=fixed_parameters,
            )
            fixed_params = {}

            if fixed_parameters:
                for item in fixed_parameters.split(","):
                    if "=" in item:
                        key, val = item.split("=", 1)
                        fixed_params[key.strip()] = float(val)

            fit_definition = FIT_DEFINITIONS.get(self._get_fit_name(fit_type))
            free_param_names = [name for name in param_names if name not in fixed_params]
            if fit_definition is not None:
                for name, value in fixed_params.items():
                    lower, upper = fit_definition.get("bounds", {}).get(name, (-np.inf, np.inf))
                    if not lower <= value <= upper:
                        raise ValueError(f"Fixed parameter {name}={value:g} must be within [{lower:g}, {upper:g}] for a {fit_type} fit.")
            if fit_definition is not None and fixed_params:
                original_fit_func = fit_func

                def fit_func(x: np.ndarray, *free_args: float) -> np.ndarray:
                    parameter_values = dict(zip(free_param_names, free_args, strict=True))
                    parameter_values.update(fixed_params)
                    return original_fit_func(x, *(parameter_values[name] for name in param_names))
            if not free_param_names:
                raise ValueError("At least one fit parameter must remain free.")
            if len(x_data) < max(MIN_FIT_POINTS, len(free_param_names)):
                raise ValueError(
                    f"At least {len(free_param_names)} data points are required for a {fit_type} fit."
                )

            initial_guess = (
                fit_definition["initial_guess"](x_data, y_data)
                if fit_definition is not None and "initial_guess" in fit_definition
                else [1] * len(param_names)
            )
            fit_options = {
                "p0": [
                    initial_guess[index]
                    for index, name in enumerate(param_names)
                    if name not in fixed_params
                ]
            }
            if fit_definition is not None and "bounds" in fit_definition:
                bounds = fit_definition["bounds"]
                fit_options["bounds"] = (
                    [bounds.get(name, (-np.inf, np.inf))[0] for name in free_param_names],
                    [bounds.get(name, (-np.inf, np.inf))[1] for name in free_param_names],
                )

            self.logger.debug("Weighted fit: %s", sigma_y is not None)

            if sigma_y is not None:
                self.logger.info(
                    "sigma_y range: %.3f - %.3f, n=%d",
                    sigma_y.min(),
                    sigma_y.max(),
                    len(sigma_y),
                )

                fit_options["sigma"] = sigma_y
                fit_options["absolute_sigma"] = True

            popt, pcov = curve_fit(
                fit_func,
                x_data,
                y_data,
                **fit_options,
            )

            perr = np.sqrt(np.diag(pcov))

            r_squared = None

            if calculate_r_squared:
                y_pred = fit_func(x_data, *popt)

                if sigma_y is not None:
                    # Weighted R-squared
                    weights = 1 / sigma_y ** 2
                    y_mean = np.sum(weights * y_data) / np.sum(weights)
                    ss_res = np.sum(weights * (y_data - y_pred) ** 2)
                    ss_tot = np.sum(weights * (y_data - y_mean) ** 2)

                else:
                    # Standard R-squared
                    ss_res = np.sum((y_data - y_pred) ** 2)
                    y_mean = np.mean(y_data)
                    ss_tot = np.sum((y_data - y_mean) ** 2)

                if ss_tot != 0:
                    r_squared = 1 - (ss_res / ss_tot)

            # Generate fit data for plotting
            x_fit = np.linspace(
                x_min if x_min is not None else x_data.min(),
                x_max if x_max is not None else x_data.max(),
                fit_points,
            )
            y_fit = fit_func(x_fit, *popt)

            confidence_lower = None
            confidence_upper = None

            if confidence_bands:
                confidence_lower, confidence_upper = (
                    self._calculate_confidence_band(
                        fit_func,
                        x_fit,
                        popt,
                        pcov,
                        x_data,
                    )
                )

            params = {}
            popt_index = 0

            for name in param_names:
                if name in fixed_params:
                    params[name] = fixed_params[name]
                else:
                    params[name] = popt[popt_index]
                    popt_index += 1

            result = FitResult(
                fit_type=fit_type,
                parameters=popt,
                errors=perr,
                param_names=param_names,
                params=params,
                r_squared=r_squared,
                x_fit=x_fit,
                y_fit=y_fit,
                x_data=x_data,
                y_data=y_data,
                covariance=pcov,
                confidence_lower=confidence_lower,
                confidence_upper=confidence_upper,
                sigma_y=sigma_y,
                equation=self.format_equation(fit_type, params, custom_function=custom_function)
            )

            return result

        except Exception:
            self.logger.exception("Fit failed for fit type %s", fit_type)
            raise

    def format_equation(self, fit_type: str, params: dict, custom_function: str | None = None) -> str:

        fit_name = self._get_fit_name(fit_type)
        if fit_name == "Custom Function":
            equation = (custom_function or "").strip()
        else:
            fit = FIT_DEFINITIONS.get(fit_name)
            if fit is None:
                return "Unknown equation"
            equation = fit["equation"]

        for name, value in params.items():
            try:
                num = float(value)
                replacement = f"{num:.6g}"
            except (ValueError, TypeError):
                replacement = str(value)

            equation = re.sub(
                rf"\b{re.escape(name)}\b",
                replacement,
                equation,
            )

        equation = equation.replace("+-", "-").replace("+ -", "-")
        return f"y = {equation}"

    def format_parameters(self, param_names, params, errors, fixed_parameters: str | None = None ) -> str:
        """format fitted parameters for display"""
        fixed_params = {}

        if fixed_parameters:
            for item in fixed_parameters.split(","):
                if "=" in item:
                    key, val = item.split("=", 1)
                    fixed_params[key.strip()] = float(val)

        lines = []
        free_index = 0

        for name in param_names:
            value = params[name]
            if name in fixed_params:
                lines.append(f"  {name} = {value:.6g}  (fixed)")
            else:
                error = errors[free_index]
                if np.isinf(error) or np.isnan(error):
                    lines.append(f"  {name} = {value:.6g}  (no error estimate)")
                else:
                    lines.append(f"  {name} = {value:.6g} ± {error:.6g}")
                free_index += 1

        return "\n".join(lines)

    def _calculate_confidence_band(self, fit_func, x_fit, popt, pcov, x_data, confidence=0.95,):
        """Calculate confidence band for fitted curve."""
        from scipy.stats import t

        y_fit = fit_func(x_fit, *popt)
        n = len(x_data)
        p = len(popt)
        dof = max(0, n - p)

        if dof <= 0:
            return None, None

        tval = t.ppf((1 + confidence) / 2.0, dof)
        eps = np.sqrt(np.finfo(float).eps)
        jacobian = np.zeros((len(x_fit), len(popt)))

        for i in range(len(popt)):
            dp = np.zeros_like(popt)
            dp[i] = eps * np.maximum(np.abs(popt[i]), 1.0)
            y1 = fit_func(x_fit, *(popt + dp))
            y2 = fit_func(x_fit, *(popt - dp))
            jacobian[:, i] = (y1 - y2) / (2 * dp[i])

        variance = np.einsum("ij,jk,ik->i", jacobian, pcov, jacobian)
        sigma = np.sqrt(np.maximum(variance, 0))
        lower = y_fit - tval * sigma
        upper = y_fit + tval * sigma

        return lower, upper

    def _extract_sigma_y(self, df, mask, series, dataset=None) -> np.ndarray | None:
        """Extract y-axis uncertainties for weighted fitting.
            Supports symmetric and asymmetric error bar configurations."""

        if series is None or dataset is None:
            return None

        # Error columns are referenced by stable id; resolve them to current
        # DataFrame names against the series' dataset (name fallback for legacy).
        from pandaplot.models.project.items.chart import resolve_series_column

        error_bars = getattr(series.style, "error_bars", None)
        y_error_column_id = getattr(error_bars, "y_error_column_id", "")
        y_error_column = getattr(error_bars, "y_error_column", "")
        y_error_minus_column_id = getattr(error_bars, "y_error_minus_column_id", "")
        y_error_minus_column = getattr(error_bars, "y_error_minus_column", "")
        plus_column = resolve_series_column(dataset, y_error_column_id, y_error_column)
        minus_column = resolve_series_column(dataset, y_error_minus_column_id, y_error_minus_column)

        # Asymmetric error bars
        if plus_column and minus_column:
            if (
                    plus_column not in df.columns
                    or minus_column not in df.columns
            ):
                return None

            sigma_plus = df.loc[mask, plus_column].to_numpy(dtype=float)
            sigma_minus = df.loc[mask, minus_column].to_numpy(dtype=float)

            # Approximate asymmetric uncertainties by their average
            sigma = 0.5 * (sigma_plus + sigma_minus)

        # Symmetric error bars
        else:
            column = plus_column

            if not column or column not in df.columns:
                return None

            sigma = df.loc[mask, column].to_numpy(dtype=float)

        if np.any(~np.isfinite(sigma)) or np.any(sigma <= 0):
            return None

        return sigma
