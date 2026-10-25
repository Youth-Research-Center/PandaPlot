"""
Types and metadata for common data preprocessing transformations.

Preprocessing transformations rescale or recenter a single numeric column so it
is ready for plotting or further analysis (for example putting several series on
a comparable scale before overlaying them on a chart). This module defines the
catalog of supported transformations together with the metadata the guided UI
needs to render inputs, plus the result container used to surface the
transformed data and the parameters that were fitted from it.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd


class PreprocessingMethod(Enum):
    """Supported preprocessing transformations."""

    CENTER = "center"
    STANDARDIZE = "standardize"
    MINMAX = "minmax"
    ROBUST = "robust"
    MAXABS = "maxabs"


@dataclass
class PreprocessingInfo:
    """Static metadata describing a preprocessing transformation."""

    method: PreprocessingMethod
    label: str
    # Short suffix appended to the source column name to name the result column.
    suffix: str
    description: str = ""
    # Human readable formula shown in the guided UI as a learning aid.
    formula: str = ""

    # Whether the transformation exposes a target output range (min-max only).
    uses_feature_range: bool = False
    default_range_min: float = 0.0
    default_range_max: float = 1.0


PREPROCESSING_METHODS: dict[PreprocessingMethod, PreprocessingInfo] = {

    PreprocessingMethod.CENTER: PreprocessingInfo(
        method=PreprocessingMethod.CENTER,
        label="Center (mean removal)",
        suffix="centered",
        formula="x - mean(x)",
        description=(
            "Subtracts the mean so the values are centered on zero. Keeps the "
            "original spread and units; only the location changes."
        ),
    ),

    PreprocessingMethod.STANDARDIZE: PreprocessingInfo(
        method=PreprocessingMethod.STANDARDIZE,
        label="Standardize (Z-score)",
        suffix="zscore",
        formula="(x - mean(x)) / std(x)",
        description=(
            "Centers on zero and scales to unit standard deviation, giving "
            "dimensionless Z-scores. Useful for comparing columns measured in "
            "different units."
        ),
    ),

    PreprocessingMethod.MINMAX: PreprocessingInfo(
        method=PreprocessingMethod.MINMAX,
        label="Min-Max scale",
        suffix="minmax",
        formula="(x - min(x)) / (max(x) - min(x))",
        description=(
            "Rescales the values linearly into a fixed range (0 to 1 by "
            "default). Preserves the shape of the distribution."
        ),
        uses_feature_range=True,
        default_range_min=0.0,
        default_range_max=1.0,
    ),

    PreprocessingMethod.ROBUST: PreprocessingInfo(
        method=PreprocessingMethod.ROBUST,
        label="Robust scale (median / IQR)",
        suffix="robust",
        formula="(x - median(x)) / IQR(x)",
        description=(
            "Centers on the median and scales by the interquartile range. "
            "Resistant to outliers, unlike mean/standard-deviation scaling."
        ),
    ),

    PreprocessingMethod.MAXABS: PreprocessingInfo(
        method=PreprocessingMethod.MAXABS,
        label="Max-Abs scale",
        suffix="maxabs",
        formula="x / max(|x|)",
        description=(
            "Divides by the largest absolute value, mapping the data into "
            "[-1, 1] without shifting it. Keeps zeros at zero and preserves "
            "sign, which suits sparse or already-centered data."
        ),
    ),
}


@dataclass
class PreprocessingResult:
    """Result of applying a preprocessing transformation to a column."""

    method: PreprocessingMethod
    source_column: str

    # The transformed values, aligned to the source series' index.
    data: pd.Series

    # Parameters fitted from the data (mean, std, min, max, median, iqr, ...).
    statistics: dict[str, float] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)

    def result_name(self) -> str:
        """Generate a default result column name."""
        suffix = PREPROCESSING_METHODS[self.method].suffix
        return f"{self.source_column}_{suffix}"


def list_methods() -> list[PreprocessingInfo]:
    """Return the catalog of transformations in display order."""
    return [PREPROCESSING_METHODS[m] for m in PreprocessingMethod]
