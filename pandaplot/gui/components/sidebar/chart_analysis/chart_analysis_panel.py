"""
Chart Analysis panel.

Runs the full set of analysis operations (derivative, integral, arc length,
smoothing, interpolation) on any series of the active chart — a plotted data
series or a fitted curve — and stores the result as a new dataset.
"""

from typing import Optional, override

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pandaplot.analysis import AnalysisType
from pandaplot.commands.composite_command import CompositeCommand
from pandaplot.commands.project.chart.analyze_chart_series_command import (
    AnalyzeChartSeriesCommand,
)
from pandaplot.commands.project.chart.create_chart_with_analysis_series_command import (
    build_quick_plot_command,
)
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.sidebar.chart.series_source_picker import (
    find_series_fit_combo_index,
    populate_chart_target_combo,
    populate_series_fit_sources,
    series_source_hint,
)
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.models.events import ChartEvents, UIEvents
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class ChartAnalysisPanel(SidebarPanel):
    """Side panel for analysis operations on chart data/fit series."""

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.current_chart: Optional[Chart] = None
        self.current_chart_id: Optional[str] = None

        self._initialize()
        self._connect_signals()
        self._update_parameters_ui()

    @override
    def _init_ui(self):
        self._init_panel_layout()
        self._set_title("🧮 Chart Analysis")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(6)

        self._create_source_section(content_layout)
        self._create_operation_section(content_layout)
        self._create_parameters_section(content_layout)
        self._create_range_section(content_layout)
        self._create_result_section(content_layout)
        self._create_preview_section(content_layout)
        self._create_action_buttons(content_layout)
        content_layout.addStretch()

        self._set_content(content, scrollable=True)

    # -- sections ---------------------------------------------------------

    def _create_source_section(self, layout):
        group = QGroupBox("Series")
        form = QFormLayout(group)
        self.source_combo = QComboBox()
        form.addRow("Analyze:", self.source_combo)
        self.source_hint = QLabel("Data series and fitted curves of this chart.")
        self.source_hint.setWordWrap(True)
        form.addRow(self.source_hint)
        layout.addWidget(group)

    def _create_operation_section(self, layout):
        group = QGroupBox("Operation")
        form = QFormLayout(group)
        self.operation_combo = QComboBox()
        self.operation_combo.addItem("Derivative", AnalysisType.DERIVATIVE)
        self.operation_combo.addItem("Integral", AnalysisType.INTEGRAL)
        self.operation_combo.addItem("Arc length (line length)", AnalysisType.ARC_LENGTH)
        self.operation_combo.addItem("Smoothing", AnalysisType.SMOOTHING)
        self.operation_combo.addItem("Interpolation", AnalysisType.INTERPOLATION)
        form.addRow("Type:", self.operation_combo)
        layout.addWidget(group)

    def _create_parameters_section(self, layout):
        self.parameters_group = QGroupBox("Parameters")
        self.parameters_layout = QFormLayout(self.parameters_group)
        layout.addWidget(self.parameters_group)

    def _create_range_section(self, layout):
        group = QGroupBox("Segment (index range)")
        form = QFormLayout(group)

        self.start_index = QSpinBox()
        self.start_index.setMinimum(0)
        self.start_index.setMaximum(0)
        self.start_value_label = QLabel("–")
        start_row = QHBoxLayout()
        start_row.addWidget(self.start_index)
        start_row.addWidget(self.start_value_label)
        form.addRow("Start index:", start_row)

        self.end_index = QSpinBox()
        self.end_index.setMinimum(0)
        self.end_index.setMaximum(0)
        self.end_value_label = QLabel("–")
        end_row = QHBoxLayout()
        end_row.addWidget(self.end_index)
        end_row.addWidget(self.end_value_label)
        form.addRow("End index:", end_row)

        layout.addWidget(group)

    def _create_result_section(self, layout):
        group = QGroupBox("Result")
        form = QFormLayout(group)
        self.result_name = QLineEdit()
        self.result_name.setPlaceholderText("Auto-named from operation and series")
        form.addRow("Dataset name:", self.result_name)
        self.plot_result_cb = QCheckBox("Plot result")
        self.plot_result_cb.setChecked(True)
        form.addRow("", self.plot_result_cb)
        self.plot_target_row = QWidget()
        target_row_layout = QHBoxLayout(self.plot_target_row)
        target_row_layout.setContentsMargins(0, 0, 0, 0)
        target_row_layout.addWidget(QLabel("Plot on:"))
        self.plot_target_combo = QComboBox()
        target_row_layout.addWidget(self.plot_target_combo)
        form.addRow("", self.plot_target_row)
        layout.addWidget(group)

    def _create_preview_section(self, layout):
        group = QGroupBox("Preview")
        vbox = QVBoxLayout(group)
        self.preview_btn = PButton("Preview", role="secondary", on_click=self.preview)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(140)
        self.preview_text.setPlaceholderText("Preview results will appear here...")
        vbox.addWidget(self.preview_btn)
        vbox.addWidget(self.preview_text)
        layout.addWidget(group)

    def _create_action_buttons(self, layout):
        row = QHBoxLayout()
        self.apply_btn = PButton("Apply", role="primary", on_click=self.apply)
        self.clear_btn = PButton("Clear", role="secondary", on_click=self.clear_inputs)
        row.addWidget(self.apply_btn)
        row.addWidget(self.clear_btn)
        layout.addLayout(row)

    def _connect_signals(self):
        self.operation_combo.currentIndexChanged.connect(self._update_parameters_ui)
        self.operation_combo.currentIndexChanged.connect(self._auto_name)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.start_index.valueChanged.connect(self._update_range_labels)
        self.end_index.valueChanged.connect(self._update_range_labels)
        self.plot_result_cb.toggled.connect(self._update_plot_target_visibility)

    # -- dynamic parameters ----------------------------------------------

    def _clear_parameters(self):
        # removeRow deletes the row's widgets synchronously (and disconnects
        # their signals), unlike takeAt + deleteLater which would leave stale
        # widgets and connections around until the event loop runs.
        while self.parameters_layout.rowCount() > 0:
            self.parameters_layout.removeRow(0)
        # Drop references so hasattr()-style checks stay honest.
        for attr in ("method_combo", "smooth_method_combo", "window_length_spin",
                     "poly_order_spin", "window_spin", "interp_method_combo",
                     "num_points_spin"):
            if hasattr(self, attr):
                delattr(self, attr)

    def _update_parameters_ui(self):
        self._clear_parameters()
        op = self.operation_combo.currentData()

        if op == AnalysisType.DERIVATIVE:
            self.method_combo = QComboBox()
            self.method_combo.addItem("Central difference", "central")
            self.method_combo.addItem("Forward difference", "forward")
            self.method_combo.addItem("Backward difference", "backward")
            self.parameters_layout.addRow("Method:", self.method_combo)

        elif op in (AnalysisType.INTEGRAL, AnalysisType.ARC_LENGTH):
            label = "Trapezoidal rule" if op == AnalysisType.INTEGRAL else "Euclidean distance"
            self.parameters_layout.addRow(QLabel(f"Method: {label}"))

        elif op == AnalysisType.SMOOTHING:
            self.smooth_method_combo = QComboBox()
            self.smooth_method_combo.addItem("Savitzky-Golay", "savgol")
            self.smooth_method_combo.addItem("Rolling mean", "rolling_mean")
            self.smooth_method_combo.addItem("LOWESS", "lowess")
            self.smooth_method_combo.currentIndexChanged.connect(self._update_smoothing_params)
            self.parameters_layout.addRow("Method:", self.smooth_method_combo)
            self._update_smoothing_params()

        elif op == AnalysisType.INTERPOLATION:
            self.interp_method_combo = QComboBox()
            for name, value in (("Linear", "linear"), ("Cubic", "cubic"),
                                ("Quadratic", "quadratic"), ("Nearest", "nearest")):
                self.interp_method_combo.addItem(name, value)
            self.parameters_layout.addRow("Method:", self.interp_method_combo)
            self.num_points_spin = QSpinBox()
            self.num_points_spin.setRange(10, 100000)
            self.num_points_spin.setValue(200)
            self.parameters_layout.addRow("Points:", self.num_points_spin)

    def _update_smoothing_params(self):
        # Remove any rows previously added below the method row.
        while self.parameters_layout.rowCount() > 1:
            self.parameters_layout.removeRow(1)
        for attr in ("window_length_spin", "poly_order_spin", "window_spin"):
            if hasattr(self, attr):
                delattr(self, attr)

        method = self.smooth_method_combo.currentData()
        if method == "savgol":
            self.window_length_spin = QSpinBox()
            self.window_length_spin.setRange(3, 101)
            self.window_length_spin.setValue(11)
            self.parameters_layout.addRow("Window length:", self.window_length_spin)
            self.poly_order_spin = QSpinBox()
            self.poly_order_spin.setRange(1, 10)
            self.poly_order_spin.setValue(3)
            self.parameters_layout.addRow("Polynomial order:", self.poly_order_spin)
        elif method == "rolling_mean":
            self.window_spin = QSpinBox()
            self.window_spin.setRange(2, 100)
            self.window_spin.setValue(5)
            self.parameters_layout.addRow("Window size:", self.window_spin)

    # -- config -----------------------------------------------------------

    def _selected_source(self):
        """Return (kind, index) for the selected series, or None."""
        return self.source_combo.currentData()

    def _build_parameters(self) -> dict:
        params: dict = {
            "start_index": self.start_index.value(),
            # end_index shown in the UI is the last included point; the
            # engine takes an exclusive slice boundary.
            "end_index": self.end_index.value() + 1,
        }
        op = self.operation_combo.currentData()
        if op == AnalysisType.DERIVATIVE and hasattr(self, "method_combo"):
            params["method"] = self.method_combo.currentData()
        elif op == AnalysisType.SMOOTHING and hasattr(self, "smooth_method_combo"):
            params["method"] = self.smooth_method_combo.currentData()
            if hasattr(self, "window_length_spin"):
                params["window_length"] = self.window_length_spin.value()
            if hasattr(self, "poly_order_spin"):
                params["polynomial_order"] = self.poly_order_spin.value()
            if hasattr(self, "window_spin"):
                params["window"] = self.window_spin.value()
        elif op == AnalysisType.INTERPOLATION and hasattr(self, "interp_method_combo"):
            params["method"] = self.interp_method_combo.currentData()
            params["num_points"] = self.num_points_spin.value()
        return params

    def _make_command(self) -> Optional[AnalyzeChartSeriesCommand]:
        source = self._selected_source()
        if source is None or self.current_chart_id is None:
            return None
        kind, index = source
        name = self.result_name.text().strip() or None
        folder_id = self.current_chart.parent_id if self.current_chart else None
        return AnalyzeChartSeriesCommand(
            self.app_context,
            chart_id=self.current_chart_id,
            source_kind=kind,
            source_index=index,
            analysis_type=self.operation_combo.currentData(),
            parameters=self._build_parameters(),
            result_name=name,
            folder_id=folder_id,
        )

    # -- actions ----------------------------------------------------------

    def preview(self):
        command = self._make_command()
        if command is None:
            self.preview_text.setText("❌ Select a series to analyze.")
            return
        try:
            df, default_name = command.run_analysis()
            lines = [
                f"Operation: {self.operation_combo.currentText()}",
                f"Series: {self.source_combo.currentText()}",
                f"Result: {len(df)} points → dataset '{self.result_name.text().strip() or default_name}'",
                "",
                "First rows:",
                df.head(5).to_string(index=False),
            ]
            self.preview_text.setText("\n".join(lines))
        except Exception as e:
            self.preview_text.setText(f"❌ Preview error: {e}")

    def apply(self):
        command = self._make_command()
        if command is None:
            self.preview_text.setText("❌ Select a series to analyze.")
            return

        executor = self.app_context.get_command_executor()
        plot_result = self.plot_result_cb.isChecked() and self.plot_result_cb.isEnabled()
        if plot_result:
            folder_id = self.current_chart.parent_id if self.current_chart else None
            plot_command = build_quick_plot_command(
                self.app_context,
                command,
                target_chart_id=self.plot_target_combo.currentData(),
                folder_id=folder_id,
            )
            success = executor.execute_command(CompositeCommand([command, plot_command]))
        else:
            success = executor.execute_command(command)

        if success:
            message = "✅ Created a new dataset from the analysis. Find it in the project explorer."
            if plot_result:
                message += " Plotted the result."
            self.preview_text.setText(message)
        else:
            self.preview_text.setText(
                "❌ Could not analyze the series. See the log for details."
            )

    def clear_inputs(self):
        self.result_name.clear()
        self.start_index.setValue(0)
        self.end_index.setValue(self.end_index.maximum())
        self.operation_combo.setCurrentIndex(0)
        self.preview_text.clear()
        self._update_range_labels()

    # -- chart context ----------------------------------------------------

    def _range_command(self, kind: str, index: int) -> Optional[AnalyzeChartSeriesCommand]:
        """Build a throwaway command to resolve the selected series.

        Used for the segment bounds and index → (x, y) previews, so both
        stay in sync with what will actually be analyzed — a data series'
        raw row count can be larger once rows with missing x/y are dropped.
        """
        if self.current_chart is None or self.current_chart_id is None:
            return None
        return AnalyzeChartSeriesCommand(
            self.app_context,
            chart_id=self.current_chart_id,
            source_kind=kind,
            source_index=index,
            analysis_type=AnalysisType.DERIVATIVE,
        )

    def _series_length(self, kind: str, index: int) -> int:
        """Best-effort length of a source series, for the segment bounds."""
        command = self._range_command(kind, index)
        return command.source_length() if command else 0

    def _on_source_changed(self):
        source = self._selected_source()
        if source is None:
            last = 0
        else:
            last = max(self._series_length(*source) - 1, 0)
        self.start_index.setMaximum(last)
        self.end_index.setMaximum(last)
        # Default to the whole series — the last included point — whenever
        # the source changes, since a previous value may no longer make
        # sense against the new series' length.
        self.end_index.setValue(last)
        self._auto_name()
        self._update_range_labels()

    def _format_point(self, point: Optional[tuple[float, float]]) -> str:
        if point is None:
            return "–"
        x, y = point
        return f"x={x:.4g}, y={y:.4g}"

    def _update_range_labels(self):
        source = self._selected_source()
        command = self._range_command(*source) if source else None
        if command is None:
            self.start_value_label.setText("–")
            self.end_value_label.setText("–")
            return

        self.start_value_label.setText(self._format_point(command.resolve_point(self.start_index.value())))
        self.end_value_label.setText(self._format_point(command.resolve_point(self.end_index.value())))

    def _auto_name(self):
        if self.source_combo.count() == 0:
            return
        op = self.operation_combo.currentText().split(" (")[0]
        # Leave any user-entered name untouched; only fill the placeholder.
        self.result_name.setPlaceholderText(f"{op} — {self.source_combo.currentText()}")

    def _update_plot_target_visibility(self):
        self.plot_target_row.setVisible(self.plot_result_cb.isChecked() and self.plot_result_cb.isEnabled())

    def _update_quick_plot_compatibility(self, *, has_sources: bool):
        self.plot_result_cb.setEnabled(has_sources)
        self._update_plot_target_visibility()

    def _populate_sources(self):
        has_sources, any_series_excluded = populate_series_fit_sources(self.source_combo, self.current_chart)
        self.apply_btn.setEnabled(has_sources)
        self.preview_btn.setEnabled(has_sources)
        self.source_hint.setText(
            series_source_hint(has_sources=has_sources, any_series_excluded=any_series_excluded)
        )
        project = self.app_context.get_app_state().current_project
        populate_chart_target_combo(self.plot_target_combo, project)
        self._update_quick_plot_compatibility(has_sources=has_sources)
        self._on_source_changed()

    @override
    def setup_event_subscriptions(self):
        self.subscribe_to_event(UIEvents.TAB_CHANGED, self._on_tab_changed)
        self.subscribe_to_event(ChartEvents.CHART_UPDATED, self._on_chart_updated)
        self.subscribe_to_event(ChartEvents.SERIES_SELECTED, self._on_series_selected_event)

    def _on_series_selected_event(self, event_data):
        """Clicking a series/fit on the chart canvas or its legend also
        selects it here, so switching from "look at it" to "analyze it"
        doesn't require re-finding the same entry in this combo."""
        chart_id = event_data.get("chart_id")
        if self.current_chart_id is None or chart_id != self.current_chart_id:
            return
        kind = event_data.get("kind")
        index = event_data.get("index")
        if kind is None or index is None:
            return
        combo_index = find_series_fit_combo_index(self.source_combo, kind, index)
        if combo_index >= 0:
            self.source_combo.setCurrentIndex(combo_index)

    def _on_tab_changed(self, event_data):
        if event_data.get("tab_type") == "chart":
            chart_id = event_data.get("tab_id")
            self.current_chart_id = chart_id
            project = self.app_context.get_app_state().current_project
            chart = project.find_item(chart_id) if project and chart_id else None
            self.current_chart = chart if isinstance(chart, Chart) else None
        else:
            self.current_chart = None
            self.current_chart_id = None
        self._populate_sources()

    def _on_chart_updated(self, event_data):
        chart = event_data.get("chart")
        if not chart or (self.current_chart_id and chart.id != self.current_chart_id):
            return
        if isinstance(chart, Chart):
            self.current_chart = chart
            self.current_chart_id = chart.id
            self._populate_sources()

    @override
    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        card_bg = palette.get("card_bg", "#ffffff")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#333333")
        secondary_fg = palette.get("secondary_fg", "#666666")

        self.setStyleSheet(f"""
            ChartAnalysisPanel {{
                background-color: {card_bg};
                color: {base_fg};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 9pt;
                color: {base_fg};
                margin-top: 5px;
                padding-top: 10px;
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: {card_bg};
            }}
        """)
        self._apply_title_theme(base_fg, card_border)
        self.source_hint.setStyleSheet(
            f"QLabel {{ color: {secondary_fg}; background-color: transparent; }}"
        )
        value_label_style = f"QLabel {{ color: {secondary_fg}; background-color: transparent; }}"
        self.start_value_label.setStyleSheet(value_label_style)
        self.end_value_label.setStyleSheet(value_label_style)
        self.plot_result_cb.setStyleSheet(f"QCheckBox {{ color: {base_fg}; background-color: transparent; }}")
