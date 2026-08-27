"""
Signal analysis engine.

Provides a unified interface for running supported signal processing
methods and returning structured results for the guided UI.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

import pandas as pd

from .signal_types import (
    SIGNAL_ANALYSES,
    SignalAnalysisResult,
    SignalAnalysisType,
)

logger = logging.getLogger(__name__)


class SignalEngine:
    """ Runs signal processing analyses and returns structured results. """

    @staticmethod
    def run_analysis(
        analysis_type: SignalAnalysisType,
        column: pd.Series,
        sampling_rate: float | None = None,
        **kwargs: Any,
    ) -> SignalAnalysisResult:
        """ Run selected signal analysis. """

        from .methods import autocorrelation, fft, peaks, psd, stft

        handler = {
            SignalAnalysisType.FFT: fft.run,
            SignalAnalysisType.STFT: stft.run,
            SignalAnalysisType.PSD: psd.run,
            SignalAnalysisType.AUTOCORRELATION: autocorrelation.run,
            SignalAnalysisType.PEAKS: peaks.run,
        }.get(analysis_type)

        if handler is None:
            raise ValueError(
                f"Unsupported signal analysis: {analysis_type}"
            )

        info = SIGNAL_ANALYSES.get(analysis_type)

        if info is None:
            raise ValueError(
                f"Missing metadata for: {analysis_type}"
            )

        SignalEngine._validate_input(
            column,
            sampling_rate,
            requires_sampling_rate=info.uses_sampling_rate,
        )

        return handler(
            column=column,
            sampling_rate=sampling_rate,
            **kwargs,
        )


    @staticmethod
    def _validate_input(
        column: pd.Series,
        sampling_rate: float | None,
        *,
        requires_sampling_rate: bool,
    ) -> None:
        """ Validate common input requirements. """

        if not isinstance(column, pd.Series):
            raise TypeError(
                "Signal input must be a pandas Series."
            )

        values = pd.to_numeric(
            column,
            errors="coerce",
        ).dropna()

        if len(values) < 2:
            raise ValueError(
                "Signal must contain at least two valid samples."
            )

        if requires_sampling_rate:
            if sampling_rate is None:
                raise ValueError(
                    "This analysis requires sampling_rate."
                )

            if sampling_rate <= 0:
                raise ValueError(
                    "Sampling rate must be greater than zero."
                )

    @staticmethod
    def available_analyses() -> Sequence[SignalAnalysisType]:
        return list(SIGNAL_ANALYSES.keys())