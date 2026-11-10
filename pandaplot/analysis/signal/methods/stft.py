""" Short-Time Fourier Transform (STFT) signal analysis. """

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import signal

from pandaplot.utils.errors import UserFacingError

from ..signal_types import SignalAnalysisResult, SignalAnalysisType


def run(
    column: pd.Series,
    sampling_rate: float,
    window: str = "hann",
    nperseg: int = 256,
    overlap: float = 0.5,
    **_: Any,
) -> SignalAnalysisResult:

    if sampling_rate <= 0:
        raise UserFacingError("Sampling rate must be greater than zero.")

    if not 0 <= overlap < 1:
        raise UserFacingError("Overlap must be between 0 and 1.")

    signal_data = (
        pd.to_numeric(column, errors="coerce")
        .dropna()
        .to_numpy(dtype=float)
    )

    if signal_data.size < nperseg:
        raise UserFacingError(
            "Signal length must be larger than the segment length."
        )

    noverlap = int(nperseg * overlap)

    frequencies, times, zxx = signal.stft(
        signal_data,
        fs=sampling_rate,
        window=window,
        nperseg=nperseg,
        noverlap=noverlap,
    )

    magnitude = np.abs(zxx)

    # Flatten time-frequency matrix into dataframe
    freq_grid, time_grid = np.meshgrid(
        frequencies,
        times,
        indexing="ij",
    )

    result_df = pd.DataFrame(
        {
            "Frequency (Hz)": freq_grid.ravel(),
            "Time (s)": time_grid.ravel(),
            "Magnitude": magnitude.ravel(),
        }
    )

    return SignalAnalysisResult(
        analysis_type=SignalAnalysisType.STFT,
        analysis_name="Short-Time Fourier Transform (STFT)",
        source_columns=[str(column.name)],
        data=result_df,
        metadata={
            "sampling_rate": sampling_rate,
            "window": window,
            "nperseg": nperseg,
            "overlap": overlap,
            "frequency_bins": len(frequencies),
            "time_bins": len(times),
        },
    )