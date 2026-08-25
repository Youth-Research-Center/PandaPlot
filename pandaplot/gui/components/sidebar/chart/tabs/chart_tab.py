"""Chart tab: chart identity fields (title, subtitle, chart type, histogram bins)."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.value_combo_box import ValueComboBox
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS, compatible_chart_types_for_series


class ChartTab(QWidget):
    """Chart-level identity: title, subtitle, chart type, and the
    histogram-only bins control (shown only when chart type is Histogram).

    Deliberately excludes `chart_style_card` (title/subtitle font size,
    figure/margin padding, size, dpi) -- that widget is built and owned by
    the Style tab, per the design doc, even though both live under a
    "Chart" umbrella conceptually.
    """

    configChanged = Signal()
    # Emitted on every chart-type change (including programmatic ones while
    # loading a chart), carrying the new ChartType value. Consumed by the
    # Style tab to hide the Line card for Scatter charts.
    chartTypeChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chart = None
        self._updating_controls = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        info_group = QGroupBox("Chart Information")
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(8)

        info_layout.addWidget(QLabel("Title:"), 0, 0)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Chart title (supports $LaTeX$ math)")
        info_layout.addWidget(self.title_edit, 0, 1, 1, 2)

        info_layout.addWidget(QLabel("Subtitle:"), 1, 0)
        self.subtitle_edit = QLineEdit()
        self.subtitle_edit.setPlaceholderText("Optional (supports $LaTeX$ math)")
        info_layout.addWidget(self.subtitle_edit, 1, 1, 1, 2)

        info_layout.addWidget(QLabel("Type:"), 2, 0)
        self.chart_type_control = ValueComboBox(
            [(spec.display_name, chart_type) for chart_type, spec in CHART_TYPE_SPECS.items()]
        )
        info_layout.addWidget(self.chart_type_control, 2, 1, 1, 2)

        self.hist_bins_label = QLabel("Bins:")
        info_layout.addWidget(self.hist_bins_label, 3, 0)
        self.hist_bins_spin = QSpinBox()
        self.hist_bins_spin.setRange(2, 200)
        self.hist_bins_spin.setValue(20)
        self.hist_bins_spin.setToolTip("Number of bins used when chart type is Histogram")
        info_layout.addWidget(self.hist_bins_spin, 3, 1)
        self._update_hist_bins_visibility()

        layout.addWidget(info_group)
        layout.addStretch(1)

        self.title_edit.textChanged.connect(self._on_field_changed)
        self.subtitle_edit.textChanged.connect(self._on_field_changed)
        self.chart_type_control.currentValueChanged.connect(self._on_chart_type_index_changed)
        self.hist_bins_spin.valueChanged.connect(self._on_field_changed)

    def _on_chart_type_index_changed(self):
        """Handle chart type combo changes.

        Retypes the chart's model (`set_chart_type`) BEFORE emitting
        `chartTypeChanged` -- listeners (style_tab's card visibility,
        data_tab's per-series fields) must see the already-retyped
        series when they react to this signal, or they read stale
        series_type/style state until an unrelated full reload happens
        to run later. `_on_field_changed()` still runs afterward for its
        other responsibilities (title/subtitle/hist_bins); its own
        `set_chart_type` call is a no-op by then since the type already
        matches.
        """
        chart_type = self.chart_type_control.currentValue()
        if self._chart is not None and chart_type:
            self._chart.set_chart_type(chart_type)
        self._update_chart_type_compatibility()
        self._update_hist_bins_visibility()
        self.chartTypeChanged.emit(chart_type)
        self._on_field_changed()

    def _update_chart_type_compatibility(self):
        """Disable chart-type options that would force-retype (and visually
        alter) this chart's ACTUAL series, not just the nominal type's
        default series type -- needed for mixed-type charts, e.g. a Scatter
        chart holding a VECTOR series must not show Bar as enabled just
        because a plain Scatter series would survive the switch.
        Recomputed on every type change, since the compatible set depends
        on the current chart's actual series.

        If the chart has no series yet, falls back to the current type's
        own default_series_type rather than treating "no series" as "every
        chart type is safe"."""
        current_type = self.chart_type_control.currentValue()
        if current_type is None:
            return
        series_types = {s.series_type for s in self._chart.data_series} if self._chart else set()
        if not series_types:
            series_types = {CHART_TYPE_SPECS[current_type].default_series_type}
        compatible = compatible_chart_types_for_series(series_types)
        model = self.chart_type_control.model()
        for index in range(self.chart_type_control.count()):
            target_type = self.chart_type_control.itemData(index)
            item = model.item(index)
            enabled = target_type in compatible
            item.setEnabled(enabled)
            if enabled:
                item.setToolTip("")
            else:
                item.setToolTip(
                    f"Switching to {CHART_TYPE_SPECS[target_type].display_name} isn't "
                    f"supported from a {CHART_TYPE_SPECS[current_type].display_name} chart"
                )

    def _update_hist_bins_visibility(self):
        """Show the Histogram Bins control only when the chart type is Histogram."""
        is_histogram = self.chart_type_control.currentValue() == ChartType.HIST
        self.hist_bins_label.setVisible(is_histogram)
        self.hist_bins_spin.setVisible(is_histogram)

    def _on_field_changed(self):
        if self._chart is None or self._updating_controls:
            return
        config = self._chart.config
        config["title"] = self.title_edit.text()
        config["subtitle"] = self.subtitle_edit.text()
        config["hist_bins"] = self.hist_bins_spin.value()
        chart_type = self.chart_type_control.currentValue()
        if chart_type:
            self._chart.set_chart_type(chart_type)
        self.configChanged.emit()

    def load(self, chart):
        previous_guard = self._updating_controls
        self._updating_controls = True
        self._chart = chart
        try:
            # Note: the Title field only affects config["title"] (what
            # renders on the chart) -- it must NOT rename the chart item in
            # the project tree, which is a separate concept controlled by
            # its own rename action.
            self.title_edit.setText(chart.config.get("title", chart.name))
            self.subtitle_edit.setText(chart.config.get("subtitle", ""))

            # chart.chart_type is already a ChartType instance -- Chart's
            # constructor coerces via ChartType(...) and raises ValueError
            # for anything the combo can't represent, so a Chart reaching
            # this method is guaranteed to carry a value setCurrentValue can
            # display (no defensive except-ValueError fallback needed here).
            self.chart_type_control.setCurrentValue(chart.chart_type)
            self._update_chart_type_compatibility()
            self._update_hist_bins_visibility()

            self.hist_bins_spin.setValue(chart.config.get("hist_bins", 20))
        finally:
            self._updating_controls = previous_guard

    def apply_to(self, chart):
        chart.config["title"] = self.title_edit.text()
        chart.config["subtitle"] = self.subtitle_edit.text()
        chart.config["hist_bins"] = self.hist_bins_spin.value()

        chart_type = self.chart_type_control.currentValue()
        if chart_type:
            chart.set_chart_type(chart_type)

    def clear(self):
        self._chart = None
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            self.title_edit.clear()
            self.subtitle_edit.clear()
            self.chart_type_control.setCurrentValue(ChartType.SCATTER)
            self._update_chart_type_compatibility()
            self.hist_bins_spin.setValue(20)
            self._update_hist_bins_visibility()
        finally:
            self._updating_controls = previous_guard

    def apply_theme(self, tokens: dict):
        self.chart_type_control.set_tokens(tokens)
