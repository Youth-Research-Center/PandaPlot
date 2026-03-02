"""Style configuration tab for chart line and marker properties."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel,
    QComboBox, QDoubleSpinBox, QGroupBox,
)
from PySide6.QtCore import Signal

from pandaplot.gui.components.sidebar.chart.color_button import ColorButton
from pandaplot.models.chart.chart_configuration import (
    LineStyleType, MarkerType, LineStyle, MarkerStyle,
)
from pandaplot.models.state.app_context import AppContext


class StyleTab(QWidget):
    """Tab widget for configuring line and marker styles."""

    style_changed = Signal()

    def __init__(self, app_context: AppContext, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Line style group
        line_group = QGroupBox("Line Style")
        line_layout = QGridLayout(line_group)

        line_layout.addWidget(QLabel("Color:"), 0, 0)
        self.line_color_button = ColorButton(self.app_context)
        line_layout.addWidget(self.line_color_button, 0, 1)

        line_layout.addWidget(QLabel("Width:"), 1, 0)
        self.line_width_spin = QDoubleSpinBox()
        self.line_width_spin.setRange(0.1, 10.0)
        self.line_width_spin.setSingleStep(0.1)
        self.line_width_spin.setValue(2.0)
        line_layout.addWidget(self.line_width_spin, 1, 1)

        line_layout.addWidget(QLabel("Style:"), 2, 0)
        self.line_style_combo = QComboBox()
        for style in LineStyleType:
            self.line_style_combo.addItem(style.value.title(), style)
        line_layout.addWidget(self.line_style_combo, 2, 1)

        line_layout.addWidget(QLabel("Transparency:"), 3, 0)
        self.line_transparency_spin = QDoubleSpinBox()
        self.line_transparency_spin.setRange(0.0, 1.0)
        self.line_transparency_spin.setSingleStep(0.1)
        self.line_transparency_spin.setValue(1.0)
        line_layout.addWidget(self.line_transparency_spin, 3, 1)

        layout.addWidget(line_group)

        # Marker style group
        marker_group = QGroupBox("Marker Style")
        marker_layout = QGridLayout(marker_group)

        marker_layout.addWidget(QLabel("Type:"), 0, 0)
        self.marker_type_combo = QComboBox()
        for marker in MarkerType:
            self.marker_type_combo.addItem(marker.value.title(), marker)
        marker_layout.addWidget(self.marker_type_combo, 0, 1)

        marker_layout.addWidget(QLabel("Size:"), 1, 0)
        self.marker_size_spin = QDoubleSpinBox()
        self.marker_size_spin.setRange(1.0, 20.0)
        self.marker_size_spin.setValue(6.0)
        marker_layout.addWidget(self.marker_size_spin, 1, 1)

        marker_layout.addWidget(QLabel("Color:"), 2, 0)
        self.marker_color_button = ColorButton(self.app_context)
        marker_layout.addWidget(self.marker_color_button, 2, 1)

        marker_layout.addWidget(QLabel("Edge Color:"), 3, 0)
        self.marker_edge_color_button = ColorButton(self.app_context, None, "#000000")
        marker_layout.addWidget(self.marker_edge_color_button, 3, 1)

        layout.addWidget(marker_group)
        layout.addStretch()

    def _connect_signals(self):
        self.line_color_button.colorChanged.connect(self.style_changed)
        self.line_width_spin.valueChanged.connect(self.style_changed)
        self.line_transparency_spin.valueChanged.connect(self.style_changed)
        self.line_style_combo.currentIndexChanged.connect(self.style_changed)

        self.marker_color_button.colorChanged.connect(self.style_changed)
        self.marker_edge_color_button.colorChanged.connect(self.style_changed)
        self.marker_size_spin.valueChanged.connect(self.style_changed)
        self.marker_type_combo.currentIndexChanged.connect(self.style_changed)

    def get_line_style(self) -> LineStyle:
        """Build a LineStyle from the current widget values."""
        return LineStyle(
            color=self.line_color_button.get_color(),
            width=self.line_width_spin.value(),
            style=self.line_style_combo.currentData() or LineStyleType.SOLID,
            transparency=self.line_transparency_spin.value(),
        )

    def set_line_style(self, style: LineStyle):
        """Populate line-style widgets from a LineStyle object."""
        self.line_color_button.set_color(style.color)
        self.line_width_spin.setValue(style.width)
        self.line_transparency_spin.setValue(style.transparency)
        for i in range(self.line_style_combo.count()):
            if self.line_style_combo.itemData(i) == style.style:
                self.line_style_combo.setCurrentIndex(i)
                break

    def get_marker_style(self) -> MarkerStyle:
        """Build a MarkerStyle from the current widget values."""
        return MarkerStyle(
            type=self.marker_type_combo.currentData() or MarkerType.CIRCLE,
            size=self.marker_size_spin.value(),
            color=self.marker_color_button.get_color(),
            edge_color=self.marker_edge_color_button.get_color(),
        )

    def set_marker_style(self, style: MarkerStyle):
        """Populate marker-style widgets from a MarkerStyle object."""
        for i in range(self.marker_type_combo.count()):
            if self.marker_type_combo.itemData(i) == style.type:
                self.marker_type_combo.setCurrentIndex(i)
                break
        self.marker_size_spin.setValue(style.size)
        self.marker_color_button.set_color(style.color)
        self.marker_edge_color_button.set_color(style.edge_color)

    def load_series_style(self, series):
        """Load style values from a data series with signals blocked."""
        self.line_color_button.blockSignals(True)
        self.line_color_button.set_color(series.color)
        self.line_color_button.blockSignals(False)

        self.line_width_spin.blockSignals(True)
        self.line_width_spin.setValue(series.line_width)
        self.line_width_spin.blockSignals(False)

        self.marker_size_spin.blockSignals(True)
        self.marker_size_spin.setValue(series.marker_size)
        self.marker_size_spin.blockSignals(False)

        self.marker_color_button.blockSignals(True)
        self.marker_color_button.set_color(series.marker_color or series.color)
        self.marker_color_button.blockSignals(False)

        self.marker_edge_color_button.blockSignals(True)
        self.marker_edge_color_button.set_color(series.marker_edge_color or '#000000')
        self.marker_edge_color_button.blockSignals(False)

        self.line_style_combo.blockSignals(True)
        for i in range(self.line_style_combo.count()):
            if self.line_style_combo.itemData(i) and self.line_style_combo.itemData(i).value == series.line_style:
                self.line_style_combo.setCurrentIndex(i)
                break
        self.line_style_combo.blockSignals(False)

        self.marker_type_combo.blockSignals(True)
        for i in range(self.marker_type_combo.count()):
            if self.marker_type_combo.itemData(i) and self.marker_type_combo.itemData(i).value == series.marker_style:
                self.marker_type_combo.setCurrentIndex(i)
                break
        self.marker_type_combo.blockSignals(False)

    def load_fit_style(self, fit):
        """Load style values from fit data with signals blocked."""
        self.line_color_button.blockSignals(True)
        self.line_color_button.set_color(fit.color)
        self.line_color_button.blockSignals(False)

        self.line_width_spin.blockSignals(True)
        self.line_width_spin.setValue(fit.line_width)
        self.line_width_spin.blockSignals(False)

        self.marker_size_spin.blockSignals(True)
        self.marker_size_spin.setValue(0.0)  # Fit lines typically don't have markers
        self.marker_size_spin.blockSignals(False)

    def apply_style_to_series(self, series):
        """Apply current style widget values to a data series."""
        series.color = self.line_color_button.get_color()
        series.marker_color = self.marker_color_button.get_color()
        series.marker_edge_color = self.marker_edge_color_button.get_color()
        series.line_width = self.line_width_spin.value()
        series.marker_size = self.marker_size_spin.value()
        if self.line_style_combo.currentData():
            series.line_style = self.line_style_combo.currentData().value
        if self.marker_type_combo.currentData():
            series.marker_style = self.marker_type_combo.currentData().value

    def apply_style_to_fit(self, fit):
        """Apply current style widget values to fit data."""
        fit.color = self.line_color_button.get_color()
        fit.line_width = self.line_width_spin.value()

    def update_color_buttons(self):
        """Update ColorButton appearances for theme changes."""
        self.line_color_button._update_appearance()
        self.marker_color_button._update_appearance()
        self.marker_edge_color_button._update_appearance()
