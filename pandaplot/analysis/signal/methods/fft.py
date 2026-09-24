""" Fast Fourier Transform (FFT) signal analysis. """

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from ..signal_types import SignalAnalysisResult, SignalAnalysisType


def run(
    column: pd.Series,
    sampling_rate: float,
    nfft: int | None = None,
    window: str = "hann",
    **_: Any,
) -> SignalAnalysisResult:
    """Compute the one-sided Fast Fourier Transform of a signal."""

    if sampling_rate <= 0:
        raise ValueError("Sampling rate must be greater than zero.")

    signal = pd.to_numeric(column, errors="coerce").dropna().to_numpy(dtype=float)

    if signal.size < 2:
        raise ValueError("Signal must contain at least two valid samples.")

    if nfft is None:
        nfft = signal.size

    if nfft < signal.size:
        nfft = int(2 ** np.ceil(np.log2(signal.size)))
        #raise ValueError("NFFT must be greater than or equal to the signal length.")

    # Remove DC component
    signal = signal - np.mean(signal)

    # Apply window
    signal = _apply_window(signal, window)

    # FFT
    spectrum = np.fft.rfft(signal, n=nfft)
    frequencies = np.fft.rfftfreq(nfft, d=1.0 / sampling_rate)
    amplitude = (2.0 / signal.size) * np.abs(spectrum)

    result_df = pd.DataFrame(
        {
            "Frequency (Hz)": frequencies,
            "Amplitude": amplitude,
        }
    )

    # Find dominant frequencies
    valid_indices = np.where(frequencies > 0)[0]

    valid_amplitude = amplitude[valid_indices]

    peaks, _properties = find_peaks(
        valid_amplitude,
        prominence=np.max(valid_amplitude) * 0.05,
    )

    if len(peaks) > 0:
        peak_indices = valid_indices[peaks]

        # sort by amplitude descending
        peak_indices = peak_indices[np.argsort(amplitude[peak_indices])[::-1]]
        peak_indices = peak_indices[:5]

    else:
        peak_indices = []

    dominant_frequencies = [(float(frequencies[i]), float(amplitude[i])) for i in peak_indices]

    return SignalAnalysisResult(
        analysis_type=SignalAnalysisType.FFT,
        analysis_name="Fast Fourier Transform (FFT)",
        source_columns=[str(column.name)],
        data=result_df,
        metadata={
            "sampling_rate": sampling_rate,
            "signal_length": len(signal),
            "nfft": nfft,
            "window": window,
            "dominant_frequencies": dominant_frequencies,
        },
    )

def _apply_window(signal: np.ndarray, window: str) -> np.ndarray:
    """
    Apply selected window function before FFT.
    """

    if window == "hann":
        w = np.hanning(len(signal))

    elif window == "hamming":
        w = np.hamming(len(signal))

    elif window == "blackman":
        w = np.blackman(len(signal))

    elif window == "boxcar":
        w = np.ones(len(signal))

    else:
        raise ValueError(
            f"Unsupported window '{window}'. "
            "Choose: hann, hamming, blackman, boxcar."
        )

    return signal * w