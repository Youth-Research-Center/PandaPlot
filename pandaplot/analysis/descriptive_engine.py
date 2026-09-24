"""
Descriptive statistics engine.

Computes the common summary statistics (central tendency, dispersion, quartiles
and distribution shape) for one or more numeric columns and returns a
:class:`DescriptiveStatsResult` so the guided UI can present the output
consistently, add it to the project as data, and generate a written report.
"""

import logging
from collections.abc import Sequence

import numpy as np
import pandas as pd

from .descriptive_types import DESCRIPTIVE_STATS, DescriptiveStatsResult

logger = logging.getLogger(__name__)


def _fmt(value: float, digits: int = 6) -> str:
    """Format a float compactly, guarding against NaN/inf."""
    if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        return "n/a"
    return f"{value:.{digits}g}"


def _clean(series: pd.Series) -> np.ndarray:
    """Coerce a column to a clean 1-D float array, dropping NaNs."""
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    return values[~np.isnan(values)]


class DescriptiveStatsEngine:
    """Computes descriptive statistics for numeric columns."""

    @staticmethod
    def describe(columns: Sequence[pd.Series], digits: int = 6) -> DescriptiveStatsResult:
        """
        Compute descriptive statistics for one or more columns.

        Args:
            columns: Data columns (as pandas Series). At least one is required.
            digits: Significant digits used when formatting values for display.

        Returns:
            A populated :class:`DescriptiveStatsResult`.

        Raises:
            ValueError: If no columns are supplied. Non-numeric columns are
                reported with a zero count rather than raising.
        """
        if not columns:
            raise ValueError("Descriptive statistics require at least one column.")

        names = [str(c.name) for c in columns]
        per_column = {
            name: DescriptiveStatsEngine._describe_one(series, digits)
            for name, series in zip(names, columns, strict=True)
        }

        # Build the tidy table: one row per statistic, one column per variable.
        rows = []
        for key, label in DESCRIPTIVE_STATS.items():
            row = {"Statistic": label}
            for name in names:
                row[name] = per_column[name][key]
            rows.append(row)
        stats = pd.DataFrame(rows, columns=["Statistic", *names])

        return DescriptiveStatsResult(
            source_columns=names,
            stats=stats,
            metadata={"digits": digits, "n_columns": len(names)},
        )

    @staticmethod
    def _describe_one(series: pd.Series, digits: int) -> dict:
        """Compute every catalogued statistic for a single column (formatted)."""
        total = len(series)
        sample = _clean(series)
        n = len(sample)

        # Counts are always meaningful, even for empty/non-numeric columns.
        result = {key: "n/a" for key in DESCRIPTIVE_STATS}
        result["count"] = str(n)
        result["missing"] = str(total - n)
        if n == 0:
            return result

        mean = float(np.mean(sample))
        # Sample (ddof=1) statistics need at least two observations.
        std = float(np.std(sample, ddof=1)) if n >= 2 else float("nan")
        variance = float(np.var(sample, ddof=1)) if n >= 2 else float("nan")
        sem = std / np.sqrt(n) if n >= 2 else float("nan")
        cv = (std / mean) if (n >= 2 and mean != 0) else float("nan")
        q1, median, q3 = (float(x) for x in np.percentile(sample, [25, 50, 75]))
        minimum, maximum = float(np.min(sample)), float(np.max(sample))

        result.update({
            "mean": _fmt(mean, digits),
            "std": _fmt(std, digits),
            "variance": _fmt(variance, digits),
            "sem": _fmt(sem, digits),
            "cv": _fmt(cv, digits),
            "min": _fmt(minimum, digits),
            "q1": _fmt(q1, digits),
            "median": _fmt(median, digits),
            "q3": _fmt(q3, digits),
            "max": _fmt(maximum, digits),
            "range": _fmt(maximum - minimum, digits),
            "iqr": _fmt(q3 - q1, digits),
            "skewness": _fmt(DescriptiveStatsEngine._skewness(sample), digits),
            "kurtosis": _fmt(DescriptiveStatsEngine._kurtosis(sample), digits),
        })
        return result

    @staticmethod
    def _skewness(sample: np.ndarray) -> float:
        """Sample skewness (bias-corrected via scipy when available)."""
        if len(sample) < 3:
            return float("nan")
        from scipy import stats

        return float(stats.skew(sample, bias=False))

    @staticmethod
    def _kurtosis(sample: np.ndarray) -> float:
        """Excess sample kurtosis (bias-corrected via scipy when available)."""
        if len(sample) < 4:
            return float("nan")
        from scipy import stats

        return float(stats.kurtosis(sample, fisher=True, bias=False))
