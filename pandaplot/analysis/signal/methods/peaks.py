""" Peak detection signal analysis. """

from __future__ import annotations

from typing import Any

import pandas as pd
from scipy import signal

from pandaplot.utils.errors import UserFacingError

from ..signal_types import SignalAnalysisResult, SignalAnalysisType


def run(
    column: pd.Series,
    height: float | None = None,
    distance: int | None = None,
    prominence: float | None = None,
    threshold: float | None = None,
    **_: Any,
) -> SignalAnalysisResult:
    """ Detect peaks in a signal."""

    signal_data = (
        pd.to_numeric(column, errors="coerce")
        .dropna()
        .to_numpy(dtype=float)
    )

    if signal_data.size < 2:
        raise UserFacingError(
            "Signal must contain at least two valid samples."
        )

    peaks, properties = signal.find_peaks(
        signal_data,
        height=height,
        distance=distance,
        prominence=prominence,
        threshold=threshold,
    )

    result = pd.DataFrame(
        {
            "Index": peaks,
            "Value": signal_data[peaks],
        }
    )

    # Add optional scipy peak properties
    if "prominences" in properties:
        result["Prominence"] = properties["prominences"]

    if "peak_heights" in properties:
        result["Height"] = properties["peak_heights"]

    if "left_thresholds" in properties:
        result["Left threshold"] = properties["left_thresholds"]

    if "right_thresholds" in properties:
        result["Right threshold"] = properties["right_thresholds"]

    return SignalAnalysisResult(
        analysis_type=SignalAnalysisType.PEAKS,
        analysis_name="Peak Detection",
        source_columns=[str(column.name)],
        data=result,
        metadata={
            "number_of_peaks": len(peaks),
            "height": height,
            "distance": distance,
            "prominence": prominence,
            "threshold": threshold,
        },
    )