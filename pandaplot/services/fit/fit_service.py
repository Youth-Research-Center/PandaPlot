import logging
import re
from dataclasses import dataclass

import numpy as np

MIN_FIT_POINTS = 2

FIT_DEFINITIONS = {
    "Linear": {
        "function": lambda x, a, b: a * x + b,
        "parameters": ["a", "b"],
        "equation": "a*x + b",
    },
    "Quadratic": {
        "function": lambda x, a, b, c: a * x ** 2 + b * x + c,
        "parameters": ["a", "b", "c"],
        "equation": "a*x**2 + b*x + c",
    },
    "Exponential": {
        "function": lambda x, a, b, c: a * np.exp(b * x) + c,
        "parameters": ["a", "b", "c"],
        "equation": "a*exp(b*x) + c",
    },
    "Power": {
        "function": lambda x, a, b, c: a * (x ** b) + c,
        "parameters": ["a", "b", "c"],
        "equation": "a*x**b + c",
    },
    "Logarithmic": {
        "function": lambda x, a, b: a * np.log(x) + b,
        "parameters": ["a", "b"],
        "equation": "a*ln(x) + b",
    },
}

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

            free_count = len([
                p for p in param_names
                if p not in fixed_params
            ])

            fit_options = {"p0": [1] * free_count}

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
