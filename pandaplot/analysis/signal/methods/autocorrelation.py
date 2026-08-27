""" Autocorrelation signal analysis. """

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..signal_types import SignalAnalysisResult, SignalAnalysisType


def run(
    column: pd.Series,
    *,
    normalize: bool = True,
    **_: Any,
) -> SignalAnalysisResult:

    signal = (
        pd.to_numeric(column, errors="coerce")
        .dropna()
        .to_numpy(dtype=float)
    )

    if signal.size < 2:
        raise ValueError(
            "Signal must contain at least two valid samples."
        )

    # Remove DC component
    signal = signal - np.mean(signal)

    correlation = np.correlate(
        signal,
        signal,
        mode="full",
    )

    # Keep only positive lags
    correlation = correlation[signal.size - 1:]

    lags = np.arange(len(correlation))

    if normalize:
        max_value = correlation[0]

        if max_value != 0:
            correlation = correlation / max_value

    result_df = pd.DataFrame(
        {
            "Lag": lags,
            "Autocorrelation": correlation,
        }
    )

    return SignalAnalysisResult(
        analysis_type=SignalAnalysisType.AUTOCORRELATION,
        analysis_name="Autocorrelation",
        source_columns=[str(column.name)],
        data=result_df,
        metadata={
            "normalized": normalize,
            "samples": signal.size,
        },
    )