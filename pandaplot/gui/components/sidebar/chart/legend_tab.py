"""Legend configuration tab for chart legend properties."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel,
    QComboBox, QSpinBox, QCheckBox, QGroupBox,
)
from PySide6.QtCore import Signal

from pandaplot.gui.components.sidebar.chart.color_button import ColorButton
from pandaplot.models.chart.chart_configuration import LegendPosition, LegendStyle
from pandaplot.models.state.app_context import AppContext


class LegendTab(QWidget):
    """Tab widget for configuring chart legend properties."""

    legend_changed = Signal()

    def __init__(self, app_context: AppContext, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        legend_group = QGroupBox("Legend")
        legend_layout = QGridLayout(legend_group)

        self.legend_show_check = QCheckBox("Show Legend")
        self.legend_show_check.setChecked(True)
        legend_layout.addWidget(self.legend_show_check, 0, 0, 1, 2)

        legend_layout.addWidget(QLabel("Position:"), 1, 0)
        self.legend_position_combo = QComboBox()
        for position in LegendPosition:
            self.legend_position_combo.addItem(position.value.title(), position)
        legend_layout.addWidget(self.legend_position_combo, 1, 1)

        legend_layout.addWidget(QLabel("Font Size:"), 2, 0)
        self.legend_font_size_spin = QSpinBox()
        self.legend_font_size_spin.setRange(6, 18)
        self.legend_font_size_spin.setValue(10)
        legend_layout.addWidget(self.legend_font_size_spin, 2, 1)

        legend_layout.addWidget(QLabel("Background:"), 3, 0)
        self.legend_bg_color_button = ColorButton(self.app_context, None, "#ffffff")
        legend_layout.addWidget(self.legend_bg_color_button, 3, 1)

        layout.addWidget(legend_group)
        layout.addStretch()

    def _connect_signals(self):
        self.legend_show_check.toggled.connect(self.legend_changed)

    def get_legend(self) -> LegendStyle:
        """Build a LegendStyle from the current widget values."""
        return LegendStyle(
            show=self.legend_show_check.isChecked(),
            position=self.legend_position_combo.currentData() or LegendPosition.UPPER_RIGHT,
            font_size=self.legend_font_size_spin.value(),
            background_color=self.legend_bg_color_button.get_color(),
        )

    def set_legend(self, style: LegendStyle):
        """Populate legend widgets from a LegendStyle object."""
        self.legend_show_check.setChecked(style.show)
        self.legend_font_size_spin.setValue(style.font_size)
        self.legend_bg_color_button.set_color(style.background_color)
        for i in range(self.legend_position_combo.count()):
            if self.legend_position_combo.itemData(i) == style.position:
                self.legend_position_combo.setCurrentIndex(i)
                break

    def apply_to_chart_config(self, config: dict):
        """Apply current legend settings to a chart config dict."""
        config['show_legend'] = self.legend_show_check.isChecked()

    def load_from_chart_config(self, config: dict):
        """Load legend settings from a chart config dict."""
        self.legend_show_check.setChecked(config.get('show_legend', True))

    def update_color_buttons(self):
        """Update ColorButton appearance for theme changes."""
        self.legend_bg_color_button._update_appearance()
