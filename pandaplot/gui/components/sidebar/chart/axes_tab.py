"""Axes configuration tab for chart X/Y axis properties."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel,
    QComboBox, QSpinBox, QCheckBox, QGroupBox, QLineEdit,
)
from PySide6.QtCore import Signal

from pandaplot.models.chart.chart_configuration import ScaleType, AxisStyle


class AxesTab(QWidget):
    """Tab widget for configuring X and Y axis properties."""

    axes_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # X Axis group
        x_axis_group = QGroupBox("X Axis")
        x_axis_layout = QGridLayout(x_axis_group)

        x_axis_layout.addWidget(QLabel("Label:"), 0, 0)
        self.x_label_edit = QLineEdit()
        x_axis_layout.addWidget(self.x_label_edit, 0, 1)

        x_axis_layout.addWidget(QLabel("Font Size:"), 1, 0)
        self.x_font_size_spin = QSpinBox()
        self.x_font_size_spin.setRange(6, 24)
        self.x_font_size_spin.setValue(12)
        x_axis_layout.addWidget(self.x_font_size_spin, 1, 1)

        x_axis_layout.addWidget(QLabel("Scale:"), 2, 0)
        self.x_scale_combo = QComboBox()
        for scale in ScaleType:
            self.x_scale_combo.addItem(scale.value.title(), scale)
        x_axis_layout.addWidget(self.x_scale_combo, 2, 1)

        self.x_grid_check = QCheckBox("Show Grid")
        self.x_grid_check.setChecked(True)
        x_axis_layout.addWidget(self.x_grid_check, 3, 0, 1, 2)

        layout.addWidget(x_axis_group)

        # Y Axis group
        y_axis_group = QGroupBox("Y Axis")
        y_axis_layout = QGridLayout(y_axis_group)

        y_axis_layout.addWidget(QLabel("Label:"), 0, 0)
        self.y_label_edit = QLineEdit()
        y_axis_layout.addWidget(self.y_label_edit, 0, 1)

        y_axis_layout.addWidget(QLabel("Font Size:"), 1, 0)
        self.y_font_size_spin = QSpinBox()
        self.y_font_size_spin.setRange(6, 24)
        self.y_font_size_spin.setValue(12)
        y_axis_layout.addWidget(self.y_font_size_spin, 1, 1)

        y_axis_layout.addWidget(QLabel("Scale:"), 2, 0)
        self.y_scale_combo = QComboBox()
        for scale in ScaleType:
            self.y_scale_combo.addItem(scale.value.title(), scale)
        y_axis_layout.addWidget(self.y_scale_combo, 2, 1)

        self.y_grid_check = QCheckBox("Show Grid")
        self.y_grid_check.setChecked(True)
        y_axis_layout.addWidget(self.y_grid_check, 3, 0, 1, 2)

        layout.addWidget(y_axis_group)
        layout.addStretch()

    def _connect_signals(self):
        self.x_label_edit.textChanged.connect(self.axes_changed)
        self.y_label_edit.textChanged.connect(self.axes_changed)
        self.x_grid_check.toggled.connect(self.axes_changed)
        self.y_grid_check.toggled.connect(self.axes_changed)

    def get_x_axis(self) -> AxisStyle:
        """Build an AxisStyle from the current X-axis widget values."""
        return AxisStyle(
            label=self.x_label_edit.text(),
            font_size=self.x_font_size_spin.value(),
            scale=self.x_scale_combo.currentData() or ScaleType.LINEAR,
            show_grid=self.x_grid_check.isChecked(),
        )

    def set_x_axis(self, style: AxisStyle):
        """Populate X-axis widgets from an AxisStyle object."""
        self.x_label_edit.setText(style.label)
        self.x_font_size_spin.setValue(style.font_size)
        self.x_grid_check.setChecked(style.show_grid)
        for i in range(self.x_scale_combo.count()):
            if self.x_scale_combo.itemData(i) == style.scale:
                self.x_scale_combo.setCurrentIndex(i)
                break

    def get_y_axis(self) -> AxisStyle:
        """Build an AxisStyle from the current Y-axis widget values."""
        return AxisStyle(
            label=self.y_label_edit.text(),
            font_size=self.y_font_size_spin.value(),
            scale=self.y_scale_combo.currentData() or ScaleType.LINEAR,
            show_grid=self.y_grid_check.isChecked(),
        )

    def set_y_axis(self, style: AxisStyle):
        """Populate Y-axis widgets from an AxisStyle object."""
        self.y_label_edit.setText(style.label)
        self.y_font_size_spin.setValue(style.font_size)
        self.y_grid_check.setChecked(style.show_grid)
        for i in range(self.y_scale_combo.count()):
            if self.y_scale_combo.itemData(i) == style.scale:
                self.y_scale_combo.setCurrentIndex(i)
                break

    def apply_to_chart_config(self, config: dict):
        """Apply current axis settings to a chart config dict."""
        config['x_label'] = self.x_label_edit.text()
        config['y_label'] = self.y_label_edit.text()
        config['show_grid'] = self.x_grid_check.isChecked() and self.y_grid_check.isChecked()

    def load_from_chart_config(self, config: dict):
        """Load axis settings from a chart config dict."""
        self.x_label_edit.setText(config.get('x_label', ''))
        self.y_label_edit.setText(config.get('y_label', ''))
        self.x_grid_check.setChecked(config.get('show_grid', True))
        self.y_grid_check.setChecked(config.get('show_grid', True))
