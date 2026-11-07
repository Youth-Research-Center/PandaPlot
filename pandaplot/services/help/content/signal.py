"""Help topics for the signal analyses.

Titles and summaries are read from ``SIGNAL_ANALYSES`` when ``topics()`` is
called, and the parameter lists follow the flags and defaults of each
``SignalAnalysisInfo``. The explanations, parameter meanings, keywords and
related links are written here.
"""

from pandaplot.analysis.signal.signal_types import SIGNAL_ANALYSES, SignalAnalysisInfo, SignalAnalysisType
from pandaplot.services.help.content.panel_defaults import (
    PEAK_MINIMUM_DISTANCE,
    PEAK_MINIMUM_HEIGHT_DEFAULT,
    PEAK_PROMINENCE_DEFAULT,
    PEAK_THRESHOLD_DEFAULT,
    SAMPLING_RATE_DATASET,
    SIGNAL_OVERLAP,
)
from pandaplot.services.help.help_types import PANEL_TOPIC_CHART_SIGNAL, PANEL_TOPIC_SIGNAL, HelpCategory, HelpTopic

SIGNAL_TOPIC_IDS: dict[SignalAnalysisType, str] = {
    SignalAnalysisType.FFT: "signal.fft",
    SignalAnalysisType.STFT: "signal.stft",
    SignalAnalysisType.PSD: "signal.psd",
    SignalAnalysisType.AUTOCORRELATION: "signal.autocorrelation",
    SignalAnalysisType.PEAKS: "signal.peaks",
}

_EXPLANATIONS: dict[SignalAnalysisType, str] = {
    SignalAnalysisType.FFT: (
        "A signal such as a sound recording or a vibration measurement is a list of values over time. The FFT shows which "
        "frequencies are inside it and how strong each one is. A clean 50 Hz hum, for example, appears as one tall spike at 50 Hz.\n\n"
        "Before the transform PandaPlot subtracts the average of the signal and multiplies it by the chosen window, which fades "
        "the signal in and out at the edges to reduce false spikes. The result has the columns Frequency (Hz) and Amplitude and "
        "covers 0 Hz up to half the sampling rate. The results box also lists up to five dominant frequencies, the strongest "
        "clear peaks of the spectrum.\n\n"
        "A longer recording gives a finer frequency resolution. A larger FFT size only interpolates the spectrum more smoothly; "
        "it does not add new information. If the FFT size is smaller than the number of samples, PandaPlot raises it to the next "
        "power of two that fits the whole signal instead of cutting data off."
    ),
    SignalAnalysisType.STFT: (
        "The FFT tells you which frequencies occur, but not when. The STFT cuts the signal into short overlapping pieces "
        "(segments), takes the FFT of each piece, and so shows how the frequencies change over time. It is the right tool for a "
        "bird call that rises in pitch or a machine that speeds up.\n\n"
        "The result has the columns Frequency (Hz), Time (s) and Magnitude, with one row for every combination of frequency and "
        "time. Short segments locate events in time more precisely but separate nearby frequencies less well; long segments do "
        "the opposite. The signal must contain at least as many samples as the segment size."
    ),
    SignalAnalysisType.PSD: (
        "The power spectral density shows how the power of a signal is spread over frequency. It is a smoother and more "
        "reliable picture of the spectrum than a single FFT, especially for noisy signals.\n\n"
        "Welch's method cuts the signal into overlapping segments, applies the window to each, and averages their spectra. "
        "Averaging reduces the random noise in the estimate. The cost is resolution: shorter segments mean fewer, wider "
        "frequency steps. If the segment size is larger than the signal, the whole signal is used as one segment. The result has "
        "the columns Frequency (Hz) and PSD."
    ),
    SignalAnalysisType.AUTOCORRELATION: (
        "Autocorrelation compares a signal with a copy of itself shifted by a number of samples (the lag). If the signal repeats "
        "every 100 samples, the autocorrelation is high again at a lag of 100. It is a simple way to find a repeating period "
        "in noisy data.\n\n"
        "PandaPlot subtracts the average first, keeps only lags of zero and above, and divides by the value at lag 0, so lag 0 "
        "is always 1 and the other values lie between -1 and 1. The lag is counted in samples, not in seconds, so multiply "
        "by the time between samples to get a period. The result has the columns Lag and Autocorrelation."
    ),
    SignalAnalysisType.PEAKS: (
        "A peak is a value that is higher than the values on both sides of it. Peak detection lists every such local maximum, "
        "which helps you count pulses, heartbeats or oscillations, and find when they happen.\n\n"
        "The result has one row per peak, with its position (Index, counted in samples from 0 after missing and non-numeric values "
        "have been dropped, so it can differ from the row number in the table), its Value and, depending on the "
        "settings, extra columns such as Prominence. The four settings only keep peaks that pass every test, so adding "
        "restrictions can only remove peaks. All four start at values that remove nothing, except that Minimum height starts "
        "at 0, which leaves out peaks lying below zero."
    ),
}

_PARAMETER_MEANINGS: dict[str, str] = {
    "sampling_rate": (
        "How many samples were recorded per second, in Hz. In the Signal Analysis panel it starts at {sampling_rate}. In the Chart Signal "
        "Analysis panel it is filled in as 1 divided by the typical (median) spacing of the x values in the segment, and stays at "
        "{sampling_rate} when that cannot be worked out. It converts positions in the list into real frequencies "
        "and times, so a wrong value gives correct-looking but mislabelled frequencies."
    ),
    "nfft": "How many points the FFT uses (default {nfft}). Larger values give a smoother-looking spectrum but no new detail.",
    "window": (
        "The shape used to fade the signal in and out at the edges of each segment (default {window}). 'hann', 'hamming' and "
        "'blackman' reduce false spikes next to strong peaks; 'boxcar' applies no fading."
    ),
    "nperseg": (
        "How many samples go into each segment (default {nperseg}). Short segments give finer timing or a smoother estimate; "
        "long segments give finer frequency detail."
    ),
    "overlap": (
        "The fraction of each segment shared with the next one, from {overlap_min:g} to {overlap_max:g} (default {overlap}). More overlap uses the data "
        "more fully but costs more computing time."
    ),
    "height": "Peaks lower than this value are ignored (default {height}). Lower it below zero to find peaks in data with negative values.",
    "distance": "The smallest allowed gap between neighbouring peaks, in samples (default {distance}). Of two peaks closer than this, only the higher one is kept.",
    "prominence": (
        "How far a peak must stand out above the surrounding signal (default {prominence}, which accepts every peak). Raising it filters out "
        "small bumps on noisy data."
    ),
    "threshold": (
        "How much higher a peak must be than each of its direct neighbours (default {threshold}, which accepts every peak). Raising it "
        "filters out peaks that sit on a flat plateau."
    ),
}

_KEYWORDS: dict[SignalAnalysisType, tuple[str, ...]] = {
    SignalAnalysisType.FFT: ("fourier", "fourier transform", "spectrum", "frequency", "frequency domain", "dominant frequency", "hz"),
    SignalAnalysisType.STFT: ("fourier", "spectrogram", "time-frequency", "time frequency", "windowed fft", "frequency over time"),
    SignalAnalysisType.PSD: ("welch", "power spectrum", "spectral density", "noise", "frequency", "power"),
    SignalAnalysisType.AUTOCORRELATION: ("acf", "correlation", "period", "periodicity", "lag", "repeating pattern", "self-similarity"),
    SignalAnalysisType.PEAKS: ("find peaks", "local maxima", "maximum", "pulses", "prominence", "count peaks"),
}

_RELATED: dict[SignalAnalysisType, tuple[SignalAnalysisType, ...]] = {
    SignalAnalysisType.FFT: (SignalAnalysisType.PSD, SignalAnalysisType.STFT, SignalAnalysisType.PEAKS),
    SignalAnalysisType.STFT: (SignalAnalysisType.FFT, SignalAnalysisType.PSD),
    SignalAnalysisType.PSD: (SignalAnalysisType.FFT, SignalAnalysisType.STFT),
    SignalAnalysisType.AUTOCORRELATION: (SignalAnalysisType.FFT, SignalAnalysisType.PEAKS),
    SignalAnalysisType.PEAKS: (SignalAnalysisType.FFT, SignalAnalysisType.AUTOCORRELATION),
}

# Parameter keys in the order the panel lists them, paired with the label it shows.
_PARAMETER_LABELS: tuple[tuple[str, str], ...] = (
    ("sampling_rate", "Sampling rate"),
    ("nfft", "FFT size"),
    ("window", "Window"),
    ("nperseg", "Segment size"),
    ("overlap", "Overlap"),
    ("height", "Minimum height"),
    ("distance", "Minimum distance"),
    ("prominence", "Prominence"),
    ("threshold", "Threshold"),
)


def _used_parameter_keys(info: SignalAnalysisInfo) -> list[str]:
    """Return the parameter keys the panel shows for an analysis, in panel order."""
    used = {
        "sampling_rate": info.uses_sampling_rate,
        "nfft": info.uses_nfft,
        "window": info.uses_window,
        "nperseg": info.uses_nperseg,
        "overlap": info.uses_overlap,
        "height": info.uses_height,
        "distance": info.uses_distance,
        "prominence": info.uses_prominence,
        "threshold": info.uses_threshold,
    }
    return [key for key, _ in _PARAMETER_LABELS if used[key]]


def _parameters(info: SignalAnalysisInfo) -> tuple[tuple[str, str], ...]:
    """List the labels the panel shows for an analysis, with their meanings."""
    labels = dict(_PARAMETER_LABELS)
    parameters = [("Signal column", "The numeric column that holds the signal. Missing values are dropped before the analysis.")]
    for key in _used_parameter_keys(info):
        meaning = _PARAMETER_MEANINGS[key].format(
            sampling_rate=SAMPLING_RATE_DATASET.default,
            nfft=info.default_nfft,
            window=info.windows[0],
            nperseg=info.default_nperseg,
            overlap=info.default_overlap,
            overlap_min=SIGNAL_OVERLAP.minimum,
            overlap_max=SIGNAL_OVERLAP.maximum,
            height=PEAK_MINIMUM_HEIGHT_DEFAULT,
            distance=PEAK_MINIMUM_DISTANCE.default,
            prominence=PEAK_PROMINENCE_DEFAULT,
            threshold=PEAK_THRESHOLD_DEFAULT,
        )
        parameters.append((labels[key], meaning))
    return tuple(parameters)


def _steps(info: SignalAnalysisInfo) -> tuple[str, ...]:
    """Build the how-to steps for an analysis from the controls its panel shows."""
    steps = [
        "Open a dataset tab and open the Signal Analysis panel in the sidebar.",
        f"In Method, choose {info.label}.",
        "Under Input, choose the Signal column.",
    ]
    labels = dict(_PARAMETER_LABELS)
    names = [labels[key] for key in _used_parameter_keys(info)]
    if names:
        steps.append(f"Under Parameters, set {', '.join(names)}.")
    steps.append("Click Run to preview the analysis in the Results box.")
    steps.append(f"Click Add to Project to save the result as a new dataset named '{info.label} [<column>]'.")
    return tuple(steps)


def topics() -> list[HelpTopic]:
    """Return the help topics of this module.

    Returns:
        One topic per signal analysis, in ``SIGNAL_ANALYSES`` order.
    """
    result: list[HelpTopic] = []
    for analysis_type, info in SIGNAL_ANALYSES.items():
        result.append(
            HelpTopic(
                id=SIGNAL_TOPIC_IDS[analysis_type],
                title=info.label,
                category=HelpCategory.SIGNAL,
                summary=info.description,
                steps=_steps(info),
                explanation=_EXPLANATIONS[analysis_type],
                parameters=_parameters(info),
                keywords=_KEYWORDS[analysis_type],
                related=(PANEL_TOPIC_SIGNAL, PANEL_TOPIC_CHART_SIGNAL, *(SIGNAL_TOPIC_IDS[t] for t in _RELATED[analysis_type])),
            )
        )
    return result
