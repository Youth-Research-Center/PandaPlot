"""
Engine for common data preprocessing transformations.

Each transformation operates on a single numeric :class:`pandas.Series`, returns
a new series aligned to the source index, and reports the parameters it fitted
from the data so they can be shown to the user. Missing values (NaN) are ignored
when fitting parameters and are passed through untransformed.
"""


import pandas as pd

from .preprocessing_types import PreprocessingMethod, PreprocessingResult


class PreprocessingEngine:
    """Core engine providing preprocessing transformations on data columns."""

    @staticmethod
    def _as_numeric(series: pd.Series) -> pd.Series:
        """Coerce a series to float, raising on non-numeric data."""
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum() == 0:
            raise ValueError(
                f"Column '{series.name}' has no numeric values to transform."
            )
        return numeric.astype(float)

    @staticmethod
    def center(series: pd.Series) -> PreprocessingResult:
        """Subtract the mean so the values are centered on zero."""
        values = PreprocessingEngine._as_numeric(series)
        mean = float(values.mean())
        result = values - mean
        return PreprocessingResult(
            method=PreprocessingMethod.CENTER,
            source_column=str(series.name),
            data=result,
            statistics={"mean": mean},
        )

    @staticmethod
    def standardize(series: pd.Series, ddof: int = 0) -> PreprocessingResult:
        """Center on zero and scale to unit standard deviation (Z-score).

        ``ddof`` is the delta degrees of freedom for the standard deviation;
        the default of 0 matches the population standard deviation used by the
        conventional Z-score.
        """
        values = PreprocessingEngine._as_numeric(series)
        mean = float(values.mean())
        std = float(values.std(ddof=ddof))
        # Guard against a constant column: leave the centered (all-zero) values
        # rather than dividing by zero.
        scale = std if std > 0 else 1.0
        result = (values - mean) / scale
        return PreprocessingResult(
            method=PreprocessingMethod.STANDARDIZE,
            source_column=str(series.name),
            data=result,
            statistics={"mean": mean, "std": std},
            metadata={"ddof": ddof, "constant_column": std == 0},
        )

    @staticmethod
    def minmax(
        series: pd.Series,
        range_min: float = 0.0,
        range_max: float = 1.0,
    ) -> PreprocessingResult:
        """Linearly rescale the values into ``[range_min, range_max]``."""
        if range_max <= range_min:
            raise ValueError(
                "Min-Max range maximum must be greater than the minimum "
                f"(got min={range_min}, max={range_max})."
            )
        values = PreprocessingEngine._as_numeric(series)
        data_min = float(values.min())
        data_max = float(values.max())
        span = data_max - data_min
        if span > 0:
            unit = (values - data_min) / span
        else:
            # Constant column: map everything to the low end of the range.
            unit = values * 0.0
        result = unit * (range_max - range_min) + range_min
        return PreprocessingResult(
            method=PreprocessingMethod.MINMAX,
            source_column=str(series.name),
            data=result,
            statistics={"min": data_min, "max": data_max},
            metadata={
                "range_min": range_min,
                "range_max": range_max,
                "constant_column": span == 0,
            },
        )

    @staticmethod
    def robust(series: pd.Series) -> PreprocessingResult:
        """Center on the median and scale by the interquartile range."""
        values = PreprocessingEngine._as_numeric(series)
        median = float(values.median())
        q1 = float(values.quantile(0.25))
        q3 = float(values.quantile(0.75))
        iqr = q3 - q1
        scale = iqr if iqr > 0 else 1.0
        result = (values - median) / scale
        return PreprocessingResult(
            method=PreprocessingMethod.ROBUST,
            source_column=str(series.name),
            data=result,
            statistics={"median": median, "q1": q1, "q3": q3, "iqr": iqr},
            metadata={"constant_column": iqr == 0},
        )

    @staticmethod
    def maxabs(series: pd.Series) -> PreprocessingResult:
        """Divide by the largest absolute value, mapping data into [-1, 1]."""
        values = PreprocessingEngine._as_numeric(series)
        max_abs = float(values.abs().max())
        scale = max_abs if max_abs > 0 else 1.0
        result = values / scale
        return PreprocessingResult(
            method=PreprocessingMethod.MAXABS,
            source_column=str(series.name),
            data=result,
            statistics={"max_abs": max_abs},
            metadata={"all_zero_column": max_abs == 0},
        )

    @staticmethod
    def transform(
        method: PreprocessingMethod,
        series: pd.Series,
        params: dict | None = None,
    ) -> PreprocessingResult:
        """Dispatch to the transformation for ``method``.

        Args:
            method: The preprocessing transformation to apply.
            series: The source column.
            params: Optional method-specific parameters (e.g. ``range_min`` and
                ``range_max`` for min-max scaling, ``ddof`` for standardize).
        """
        params = params or {}

        if method == PreprocessingMethod.CENTER:
            return PreprocessingEngine.center(series)
        if method == PreprocessingMethod.STANDARDIZE:
            return PreprocessingEngine.standardize(
                series, ddof=params.get("ddof", 0)
            )
        if method == PreprocessingMethod.MINMAX:
            return PreprocessingEngine.minmax(
                series,
                range_min=params.get("range_min", 0.0),
                range_max=params.get("range_max", 1.0),
            )
        if method == PreprocessingMethod.ROBUST:
            return PreprocessingEngine.robust(series)
        if method == PreprocessingMethod.MAXABS:
            return PreprocessingEngine.maxabs(series)

        raise ValueError(f"Unknown preprocessing method: {method}")
