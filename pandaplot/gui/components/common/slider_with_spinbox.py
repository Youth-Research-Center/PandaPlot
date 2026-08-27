from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QSlider, QWidget

_DEFAULT_STEPS = 100


def slider_to_value(slider_pos: int, minimum: float, maximum: float, steps: int) -> float:
    """Map an integer slider position [0, steps] onto [minimum, maximum]."""
    fraction = slider_pos / steps
    return minimum + fraction * (maximum - minimum)


def value_to_slider(value: float, minimum: float, maximum: float, steps: int) -> int:
    """Map a float value onto an integer slider position [0, steps], clamped."""
    if maximum == minimum:
        return 0
    fraction = (value - minimum) / (maximum - minimum)
    fraction = max(0.0, min(1.0, fraction))
    return round(fraction * steps)


class SliderWithSpinbox(QWidget):
    """Track+knob slider paired with a synced numeric spinbox."""

    valueChanged = Signal(float)

    def __init__(
        self, minimum: float, maximum: float, decimals: int = 1, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._steps = _DEFAULT_STEPS
        self._updating = False

        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.setRange(0, self._steps)

        self._spinbox = QDoubleSpinBox(self)
        self._spinbox.setDecimals(decimals)
        self._spinbox.setRange(minimum, maximum)
        self._spinbox.setFixedWidth(72)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._slider, stretch=1)
        layout.addWidget(self._spinbox)

        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spinbox.valueChanged.connect(self._on_spinbox_changed)

    def value(self) -> float:
        return self._spinbox.value()

    def setValue(self, value: float):  # noqa: N802
        self._set_value(value, emit=False)

    def set_tokens(self, tokens: dict):
        pass  # slider/spinbox track color handled by global QSS; placeholder for interface parity

    def _on_slider_changed(self, slider_pos: int):
        if self._updating:
            return
        value = slider_to_value(slider_pos, self._minimum, self._maximum, self._steps)
        self._set_value(value, emit=True)

    def _on_spinbox_changed(self, value: float):
        if self._updating:
            return
        self._set_value(value, emit=True)

    def _set_value(self, value: float, *, emit: bool):
        self._updating = True
        self._spinbox.setValue(value)
        self._slider.setValue(value_to_slider(value, self._minimum, self._maximum, self._steps))
        self._updating = False
        if emit:
            self.valueChanged.emit(self._spinbox.value())
