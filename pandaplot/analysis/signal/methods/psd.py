""" Power Spectral Density (PSD) signal analysis using Welch method. """

from __future__ import annotations

from typing import Any

import pandas as pd
from scipy import signal

from ..signal_types import SignalAnalysisResult, SignalAnalysisType


def run(
    column: pd.Series,
    sampling_rate: float,
    window: str = "hann",
    nperseg: int = 256,
    overlap: float = 0.5,
    **_: Any,
) -> SignalAnalysisResult:
    """ Compute Power Spectral Density using Welch's method. """

    if sampling_rate <= 0:
        raise ValueError("Sampling rate must be greater than zero.")

    if not 0 <= overlap < 1:
        raise ValueError("Overlap must be between 0 and 1.")

    signal_data = (
        pd.to_numeric(column, errors="coerce")
        .dropna()
        .to_numpy(dtype=float)
    )

    if signal_data.size < 2:
        raise ValueError(
            "Signal must contain at least two valid samples."
        )

    nperseg = min(nperseg, signal_data.size)

    noverlap = int(nperseg * overlap)

    frequencies, power = signal.welch(
        signal_data,
        fs=sampling_rate,
        window=window,
        nperseg=nperseg,
        noverlap=noverlap,
    )

    result_df = pd.DataFrame(
        {
            "Frequency (Hz)": frequencies,
            "PSD": power,
        }
    )

    return SignalAnalysisResult(
        analysis_type=SignalAnalysisType.PSD,
        analysis_name="Power Spectral Density (Welch)",
        source_columns=[str(column.name)],
        data=result_df,
        metadata={
            "sampling_rate": sampling_rate,
            "window": window,
            "nperseg": nperseg,
            "overlap": overlap,
            "frequency_bins": len(frequencies),
        },
    )