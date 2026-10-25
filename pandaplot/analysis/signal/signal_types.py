"""
Types and metadata for guided signal analysis.

This module defines the catalog of supported signal analyses together with
the metadata the guided UI needs to render inputs and parameter widgets,
plus the result container used to surface analysis output in the application.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd


class SignalAnalysisType(Enum):
    """Supported signal analyses."""

    FFT = "fft"
    STFT = "stft"
    PSD = "psd"
    AUTOCORRELATION = "autocorrelation"
    PEAKS = "peaks"


class InputMode(Enum):
    """How many signal columns an analysis consumes."""

    ONE = "one"
    TWO = "two"

@dataclass
class SignalAnalysisInfo:
    """Static metadata describing a signal analysis."""

    analysis_type: SignalAnalysisType
    label: str
    input_mode: InputMode

    description: str = ""

    # Common parameters
    uses_sampling_rate: bool = False

    # FFT
    uses_nfft: bool = False
    default_nfft: int = 1024

    # STFT / PSD
    uses_window: bool = False
    uses_nperseg: bool = False
    uses_overlap: bool = False

    # Peak detection
    uses_height: bool = False
    uses_distance: bool = False
    uses_prominence: bool = False
    uses_threshold: bool = False

    # UI defaults
    windows: list[str] = field(
        default_factory=lambda: [
            "hann",
            "hamming",
            "blackman",
            "boxcar",
        ]
    )

    default_nperseg: int = 256
    default_overlap: float = 0.5

SIGNAL_ANALYSES: dict[SignalAnalysisType, SignalAnalysisInfo] = {

    SignalAnalysisType.FFT: SignalAnalysisInfo(
        analysis_type=SignalAnalysisType.FFT,
        label="Fast Fourier Transform (FFT)",
        input_mode=InputMode.ONE,
        uses_sampling_rate=True,
        uses_window=True,
        uses_nfft=True,
        default_nfft=1024,
        description=(
            "Transforms a signal from the time domain into the frequency "
            "domain and returns its frequency spectrum."
        ),
    ),

    SignalAnalysisType.STFT: SignalAnalysisInfo(
        analysis_type=SignalAnalysisType.STFT,
        label="Short-Time Fourier Transform (STFT)",
        input_mode=InputMode.ONE,
        uses_sampling_rate=True,
        uses_window=True,
        uses_nperseg=True,
        uses_overlap=True,
        description=(
            "Computes the time-frequency representation of a signal by "
            "performing FFT on overlapping windows."
        ),
    ),

    SignalAnalysisType.PSD: SignalAnalysisInfo(
        analysis_type=SignalAnalysisType.PSD,
        label="Power Spectral Density (Welch)",
        input_mode=InputMode.ONE,
        uses_sampling_rate=True,
        uses_window=True,
        uses_nperseg=True,
        uses_overlap=True,
        description=(
            "Estimates the signal power spectral density using Welch's method."
        ),
    ),

    SignalAnalysisType.AUTOCORRELATION: SignalAnalysisInfo(
        analysis_type=SignalAnalysisType.AUTOCORRELATION,
        label="Autocorrelation",
        input_mode=InputMode.ONE,
        description=(
            "Measures the similarity of a signal with delayed versions of itself."
        ),
    ),

    SignalAnalysisType.PEAKS: SignalAnalysisInfo(
        analysis_type=SignalAnalysisType.PEAKS,
        label="Peak Detection",
        input_mode=InputMode.ONE,
        uses_height=True,
        uses_distance=True,
        uses_prominence=True,
        uses_threshold=True,
        description=(
            "Detect local maxima (peaks) in a signal. "
            "Useful for identifying events, pulses and periodic behaviour."
        ),
    ),
}


@dataclass
class SignalAnalysisResult:
    """Result of a signal analysis."""

    analysis_type: SignalAnalysisType
    analysis_name: str

    source_columns: list[str]

    data: pd.DataFrame

    metadata: dict[str, Any] = field(default_factory=dict)

    def result_name(self) -> str:
        """Generate a default dataset name."""
        cols = ", ".join(self.source_columns)
        return f"{self.analysis_name} [{cols}]"