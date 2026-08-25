"""
Chart Analysis panel.

Runs the full set of analysis operations (derivative, integral, arc length,
smoothing, interpolation) on any series of the active chart — a plotted data
series or a fitted curve — and stores the result as a new dataset.
"""

from typing import Optional, override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pandaplot.analysis import AnalysisType
from pandaplot.commands.project.chart.analyze_chart_series_command import (
    AnalyzeChartSeriesCommand,
)
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events import ChartEvents, UIEvents
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class ChartAnalysisPanel(PWidget):
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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.title_label = QLabel("🧮 Chart Analysis")
        main_layout.addWidget(self.title_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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

        scroll_area.setWidget(content)
        main_layout.addWidget(scroll_area)

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
        layout.addWidget(group)

    def _create_preview_section(self, layout):
        group = QGroupBox("Preview")
        vbox = QVBoxLayout(group)
        self.preview_btn = QPushButton("🔍 Preview")
        self.preview_btn.clicked.connect(self.preview)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(140)
        self.preview_text.setPlaceholderText("Preview results will appear here...")
        vbox.addWidget(self.preview_btn)
        vbox.addWidget(self.preview_text)
        layout.addWidget(group)

    def _create_action_buttons(self, layout):
        row = QHBoxLayout()
        self.apply_btn = QPushButton("✅ Analyze → New Dataset")
        self.apply_btn.clicked.connect(self.apply)
        self.clear_btn = QPushButton("🔄 Clear")
        self.clear_btn.clicked.connect(self.clear_inputs)
        row.addWidget(self.apply_btn)
        row.addWidget(self.clear_btn)
        layout.addLayout(row)

    def _connect_signals(self):
        self.operation_combo.currentIndexChanged.connect(self._update_parameters_ui)
        self.operation_combo.currentIndexChanged.connect(self._auto_name)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.start_index.valueChanged.connect(self._update_range_labels)
        self.end_index.valueChanged.connect(self._update_range_labels)

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
        return AnalyzeChartSeriesCommand(
            self.app_context,
            chart_id=self.current_chart_id,
            source_kind=kind,
            source_index=index,
            analysis_type=self.operation_combo.currentData(),
            parameters=self._build_parameters(),
            result_name=name,
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
        if self.app_context.get_command_executor().execute_command(command):
            self.preview_text.setText(
                "✅ Created a new dataset from the analysis. Find it in the project explorer."
            )
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

    def _populate_sources(self):
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        chart = self.current_chart
        if chart is not None:
            for i, series in enumerate(chart.data_series):
                label = series.label or f"Series {i + 1}"
                self.source_combo.addItem(f"📈 {label}", ("series", i))
            for i, fit in enumerate(chart.fit_data):
                label = fit.label or f"Fit {i + 1}"
                self.source_combo.addItem(f"〰 {label}  (fit)", ("fit", i))
        self.source_combo.blockSignals(False)

        has_sources = self.source_combo.count() > 0
        self.apply_btn.setEnabled(has_sources)
        self.preview_btn.setEnabled(has_sources)
        if not has_sources:
            self.source_hint.setText("This chart has no data series or fits yet.")
        else:
            self.source_hint.setText("Data series and fitted curves of this chart.")
        self._on_source_changed()

    @override
    def setup_event_subscriptions(self):
        self.subscribe_to_event(UIEvents.TAB_CHANGED, self._on_tab_changed)
        self.subscribe_to_event(ChartEvents.CHART_UPDATED, self._on_chart_updated)

    def _on_tab_changed(self, event_data):
        if event_data.get("tab_type") == "chart":
            chart_id = event_data.get("chart_id")
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
        accent = palette.get("accent", "#4CAF50")
        card_hover = palette.get("card_hover", "#e5f3ff")

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
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: bold;
                color: {base_fg};
                padding: 5px;
                background-color: {card_border};
                border-radius: 3px;
            }}
        """)
        self.source_hint.setStyleSheet(
            f"QLabel {{ color: {secondary_fg}; background-color: transparent; }}"
        )
        value_label_style = f"QLabel {{ color: {secondary_fg}; background-color: transparent; }}"
        self.start_value_label.setStyleSheet(value_label_style)
        self.end_value_label.setStyleSheet(value_label_style)
        self.apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {card_hover}; color: {base_fg}; }}
            QPushButton:disabled {{ background-color: {secondary_fg}; color: #999999; }}
        """)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {secondary_fg};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #7f8c8d; }}
        """)
