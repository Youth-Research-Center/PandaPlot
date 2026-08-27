"""Legend tab: chart legend visibility, position, columns, frame, background."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.card import Card
from pandaplot.gui.components.common.color_swatch_row import ColorSwatchRow
from pandaplot.gui.components.common.font_family_options import list_available_font_families
from pandaplot.gui.components.common.section_header import SectionHeader
from pandaplot.gui.components.common.segmented_control import SegmentedControl
from pandaplot.gui.components.common.slider_with_spinbox import SliderWithSpinbox
from pandaplot.gui.components.common.toggle_switch import ToggleSwitch
from pandaplot.gui.components.common.value_combo_box import ValueComboBox
from pandaplot.models.chart.chart_configuration import LegendPosition


class LegendTab(QWidget):
    """Legend visibility/position/frame/background configuration."""

    configChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chart = None
        self._updating_controls = False

        layout = QVBoxLayout(self)

        show_row = QHBoxLayout()
        show_row.addWidget(QLabel("Show legend"))
        self.show_legend_toggle = ToggleSwitch(checked=True)
        show_row.addWidget(self.show_legend_toggle)
        show_row.addStretch(1)
        layout.addLayout(show_row)

        self.legend_group = QGroupBox("Legend")
        legend_layout = QGridLayout(self.legend_group)

        legend_layout.addWidget(QLabel("Position:"), 0, 0)
        self.legend_position_combo = QComboBox()
        for position in LegendPosition:
            self.legend_position_combo.addItem(position.value.title(), position.value)
        for label, value in [
            ("Outside Right", "outside_right"),
            ("Outside Top", "outside_top"),
            ("Outside Bottom", "outside_bottom"),
            ("Custom...", "custom"),
        ]:
            self.legend_position_combo.addItem(label, value)
        legend_layout.addWidget(self.legend_position_combo, 0, 1)

        self.legend_custom_row = QWidget()
        custom_layout = QGridLayout(self.legend_custom_row)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.addWidget(QLabel("X:"), 0, 0)
        self.legend_custom_x_spin = QDoubleSpinBox()
        self.legend_custom_x_spin.setRange(0.0, 1.0)
        self.legend_custom_x_spin.setSingleStep(0.05)
        self.legend_custom_x_spin.setValue(1.02)
        custom_layout.addWidget(self.legend_custom_x_spin, 0, 1)
        custom_layout.addWidget(QLabel("Y:"), 1, 0)
        self.legend_custom_y_spin = QDoubleSpinBox()
        self.legend_custom_y_spin.setRange(0.0, 1.0)
        self.legend_custom_y_spin.setSingleStep(0.05)
        self.legend_custom_y_spin.setValue(0.5)
        custom_layout.addWidget(self.legend_custom_y_spin, 1, 1)
        custom_layout.addWidget(QLabel("Anchor:"), 2, 0)
        self.legend_custom_anchor_combo = QComboBox()
        for anchor in ("upper left", "upper right", "lower left", "lower right", "center",
                       "center left", "center right", "upper center", "lower center"):
            self.legend_custom_anchor_combo.addItem(anchor.title(), anchor)
        custom_layout.addWidget(self.legend_custom_anchor_combo, 2, 1)
        legend_layout.addWidget(self.legend_custom_row, 1, 0, 1, 2)
        self.legend_custom_row.setVisible(False)

        legend_layout.addWidget(QLabel("Font Size:"), 2, 0)
        self.legend_font_size_spin = QSpinBox()
        self.legend_font_size_spin.setRange(6, 18)
        self.legend_font_size_spin.setValue(10)
        legend_layout.addWidget(self.legend_font_size_spin, 2, 1)

        legend_layout.addWidget(QLabel("Columns:"), 3, 0)
        self.legend_columns_control = SegmentedControl([("1", 1), ("2", 2), ("3", 3)])
        legend_layout.addWidget(self.legend_columns_control, 3, 1)

        legend_layout.addWidget(QLabel("Font family:"), 4, 0)
        self.legend_font_family_combo = ValueComboBox(list_available_font_families())
        legend_layout.addWidget(self.legend_font_family_combo, 4, 1)

        layout.addWidget(self.legend_group)

        self.frame_card = Card()
        frame_layout = QGridLayout(self.frame_card)
        self.frame_header = SectionHeader("Frame")
        frame_layout.addWidget(self.frame_header, 0, 0)
        self.legend_show_frame_toggle = ToggleSwitch(checked=True)
        frame_layout.addWidget(self.legend_show_frame_toggle, 0, 1)
        self.legend_bg_color_label = QLabel("Background:")
        frame_layout.addWidget(self.legend_bg_color_label, 1, 0)
        self.legend_bg_color_row = ColorSwatchRow(["#FFFFFF", "#F4F5F8", "#1C1E26"])
        frame_layout.addWidget(self.legend_bg_color_row, 1, 1)
        self.legend_bg_opacity_label = QLabel("Opacity:")
        frame_layout.addWidget(self.legend_bg_opacity_label, 2, 0)
        self.legend_bg_opacity_slider = SliderWithSpinbox(minimum=0.0, maximum=1.0, decimals=2)
        frame_layout.addWidget(self.legend_bg_opacity_slider, 2, 1)
        layout.addWidget(self.frame_card)

        layout.addStretch()

        self.show_legend_toggle.toggled.connect(self._on_show_legend_toggled)
        self.legend_position_combo.currentIndexChanged.connect(self._on_position_changed)
        self.legend_custom_x_spin.valueChanged.connect(self._on_field_changed)
        self.legend_custom_y_spin.valueChanged.connect(self._on_field_changed)
        self.legend_custom_anchor_combo.currentIndexChanged.connect(self._on_field_changed)
        self.legend_font_size_spin.valueChanged.connect(self._on_field_changed)
        self.legend_columns_control.currentValueChanged.connect(self._on_field_changed)
        self.legend_font_family_combo.currentValueChanged.connect(self._on_field_changed)
        self.legend_show_frame_toggle.toggled.connect(self._on_field_changed)
        self.legend_show_frame_toggle.toggled.connect(self._on_frame_enabled_toggled)
        self.legend_bg_color_row.colorChanged.connect(self._on_field_changed)
        self.legend_bg_opacity_slider.valueChanged.connect(self._on_field_changed)

    def _on_position_changed(self):
        self.legend_custom_row.setVisible(self.legend_position_combo.currentData() == "custom")
        self._on_field_changed()

    def _on_show_legend_toggled(self, _checked: bool):  # noqa: FBT001 - Qt signal-slot callback, called positionally
        self._update_legend_controls_visibility()
        self._on_field_changed()

    def _update_legend_controls_visibility(self):
        """Hide (not just grey) the Legend and Frame sections entirely when
        the master "Show legend" toggle is off -- reported live: "if I
        disable show legend I can still see all of the legend options."
        Hiding the whole legend_group/frame_card containers is simpler and
        cleaner than hiding a dozen individual rows inside a QGroupBox, and
        there is nothing meaningful to configure about the frame of a legend
        that isn't shown at all."""
        show_legend = self.show_legend_toggle.isChecked()
        self.legend_group.setVisible(show_legend)
        self.frame_card.setVisible(show_legend)
        if show_legend:
            self._update_frame_controls_visibility()

    def _update_frame_controls_visibility(self):
        """Hide (not just grey) the Frame section's Background/Opacity rows
        when "Show Frame" is off, greying only the section title via
        SectionHeader's disabled-state CSS -- reported live: "if I disable
        show frame, I can still see controls and edit them." Mirrors the
        same convention already established for the Style tab's Marker/
        Fill/Confidence Band sections."""
        frame_enabled = self.legend_show_frame_toggle.isChecked()
        self.frame_header.setEnabled(frame_enabled)
        for widget in (
            self.legend_bg_color_label, self.legend_bg_color_row,
            self.legend_bg_opacity_label, self.legend_bg_opacity_slider,
        ):
            widget.setVisible(frame_enabled)

    def _on_frame_enabled_toggled(self, _checked: bool):  # noqa: FBT001 - Qt signal-slot callback, called positionally
        self._update_frame_controls_visibility()

    def _on_field_changed(self):
        if self._chart is None or self._updating_controls:
            return
        config = self._chart.config
        config["show_legend"] = self.show_legend_toggle.isChecked()
        if self.legend_position_combo.currentData():
            config["legend_position"] = self.legend_position_combo.currentData()
        config["legend_font_size"] = self.legend_font_size_spin.value()
        config["legend_columns"] = self.legend_columns_control.currentValue()
        config["legend_font_family"] = self.legend_font_family_combo.currentValue()
        config["legend_show_frame"] = self.legend_show_frame_toggle.isChecked()
        config["legend_bg_color"] = self.legend_bg_color_row.currentColor()
        config["legend_bg_alpha"] = self.legend_bg_opacity_slider.value()
        config["legend_custom_x"] = self.legend_custom_x_spin.value()
        config["legend_custom_y"] = self.legend_custom_y_spin.value()
        config["legend_custom_anchor"] = self.legend_custom_anchor_combo.currentData()
        self.configChanged.emit()

    def load(self, chart):
        previous_guard = self._updating_controls
        self._updating_controls = True
        self._chart = chart
        try:
            config = chart.config
            self.show_legend_toggle.setChecked(checked=config.get("show_legend", True))
            legend_position_value = config.get("legend_position", "upper right")
            position_index = self.legend_position_combo.findData(legend_position_value)
            self.legend_position_combo.setCurrentIndex(position_index if position_index >= 0 else 0)
            self.legend_custom_x_spin.setValue(config.get("legend_custom_x", 1.02))
            self.legend_custom_y_spin.setValue(config.get("legend_custom_y", 0.5))
            anchor_index = self.legend_custom_anchor_combo.findData(config.get("legend_custom_anchor", "center left"))
            self.legend_custom_anchor_combo.setCurrentIndex(anchor_index if anchor_index >= 0 else 0)
            self.legend_custom_row.setVisible(legend_position_value == "custom")
            self.legend_font_size_spin.setValue(config.get("legend_font_size", 10))
            self.legend_columns_control.setCurrentValue(config.get("legend_columns", 1))
            self.legend_font_family_combo.setCurrentValue(config.get("legend_font_family", "DejaVu Sans"))
            self.legend_show_frame_toggle.setChecked(checked=config.get("legend_show_frame", True))
            self.legend_bg_color_row.setCurrentColor(config.get("legend_bg_color", "#ffffff"))
            self.legend_bg_opacity_slider.setValue(config.get("legend_bg_alpha", 1.0))
            self._update_legend_controls_visibility()
        finally:
            self._updating_controls = previous_guard

    def apply_to(self, chart):
        chart.config["show_legend"] = self.show_legend_toggle.isChecked()
        if self.legend_position_combo.currentData():
            chart.config["legend_position"] = self.legend_position_combo.currentData()
        chart.config["legend_font_size"] = self.legend_font_size_spin.value()
        chart.config["legend_columns"] = self.legend_columns_control.currentValue()
        chart.config["legend_font_family"] = self.legend_font_family_combo.currentValue()
        chart.config["legend_show_frame"] = self.legend_show_frame_toggle.isChecked()
        chart.config["legend_bg_color"] = self.legend_bg_color_row.currentColor()
        chart.config["legend_bg_alpha"] = self.legend_bg_opacity_slider.value()
        chart.config["legend_custom_x"] = self.legend_custom_x_spin.value()
        chart.config["legend_custom_y"] = self.legend_custom_y_spin.value()
        chart.config["legend_custom_anchor"] = self.legend_custom_anchor_combo.currentData()

    def clear(self):
        self._chart = None
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            self.show_legend_toggle.setChecked(checked=True)
            self.legend_columns_control.setCurrentValue(1)
            self.legend_font_family_combo.setCurrentValue("DejaVu Sans")
            self.legend_show_frame_toggle.setChecked(checked=True)
            self.legend_bg_color_row.setCurrentColor("#ffffff")
            self.legend_bg_opacity_slider.setValue(1.0)
            self._update_legend_controls_visibility()
        finally:
            self._updating_controls = previous_guard

    def apply_theme(self, tokens: dict):
        self.show_legend_toggle.set_tokens(tokens)
        self.legend_columns_control.set_tokens(tokens)
        self.legend_show_frame_toggle.set_tokens(tokens)
        self.legend_bg_color_row.set_tokens(tokens)
        self.legend_bg_opacity_slider.set_tokens(tokens)
