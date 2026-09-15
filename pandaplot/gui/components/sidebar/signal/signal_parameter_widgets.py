from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QSpinBox, QWidget

from pandaplot.analysis.signal.signal_types import SignalAnalysisInfo


def build_signal_parameter_widgets(
    parameters_layout: QFormLayout, info: SignalAnalysisInfo
) -> dict[str, QWidget]:
    """(Re)populate parameters_layout with the widgets `info` calls for
    (sampling rate / FFT size / window / segment size / overlap / peak-
    detection height/distance/prominence/threshold), and return them keyed
    by a stable name so callers can wire up dispatch params.

    Does NOT clear parameters_layout first -- callers own that (they may
    also need to clear/rebuild other rows, e.g. the smoothing sub-params
    row in ChartAnalysisPanel-style callers).
    """
    widgets: dict[str, QWidget] = {}

    # Sampling rate
    if info.uses_sampling_rate:
        sampling_rate = QDoubleSpinBox()
        sampling_rate.setRange(0.001, 1e9)
        sampling_rate.setValue(1000)

        parameters_layout.addRow(
            "Sampling rate:",
            sampling_rate
        )
        widgets["sampling_rate"] = sampling_rate

    # FFT size
    if info.uses_nfft:
        nfft_spin = QSpinBox()
        nfft_spin.setRange(16, 1_000_000)
        nfft_spin.setValue(info.default_nfft)
        parameters_layout.addRow(
            "FFT size:",
            nfft_spin
        )
        widgets["nfft"] = nfft_spin

    # Window
    if info.uses_window:
        window_combo = QComboBox()

        window_combo.addItems(
            info.windows
        )

        parameters_layout.addRow(
            "Window:",
            window_combo
        )
        widgets["window"] = window_combo

    # STFT / PSD
    if info.uses_nperseg:
        nperseg_spin = QSpinBox()
        nperseg_spin.setRange(8, 1_000_000)
        nperseg_spin.setValue(
            info.default_nperseg
        )

        parameters_layout.addRow(
            "Segment size:",
            nperseg_spin
        )
        widgets["nperseg"] = nperseg_spin

    if info.uses_overlap:
        overlap_spin = QDoubleSpinBox()
        overlap_spin.setRange(0.0, 0.99)
        overlap_spin.setSingleStep(0.05)
        overlap_spin.setValue(
            info.default_overlap
        )

        parameters_layout.addRow(
            "Overlap:",
            overlap_spin
        )
        widgets["overlap"] = overlap_spin

    # Peak detection
    if info.uses_height:
        height_spin = QDoubleSpinBox()
        height_spin.setRange(
            -1e12,
            1e12
        )

        parameters_layout.addRow(
            "Minimum height:",
            height_spin
        )
        widgets["height"] = height_spin

    if info.uses_distance:
        distance_spin = QSpinBox()
        distance_spin.setRange(
            1,
            1_000_000
        )
        distance_spin.setValue(1)

        parameters_layout.addRow(
            "Minimum distance:",
            distance_spin
        )
        widgets["distance"] = distance_spin

    if info.uses_prominence:
        prominence_spin = QDoubleSpinBox()
        prominence_spin.setRange(
            0,
            1e12
        )

        parameters_layout.addRow(
            "Prominence:",
            prominence_spin
        )
        widgets["prominence"] = prominence_spin

    if info.uses_threshold:
        threshold_spin = QDoubleSpinBox()
        threshold_spin.setRange(
            -1e12,
            1e12
        )

        parameters_layout.addRow(
            "Threshold:",
            threshold_spin
        )
        widgets["threshold"] = threshold_spin

    return widgets
