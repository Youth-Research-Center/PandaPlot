from typing import List, Optional, override

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pandaplot.analysis import SIGNAL_ANALYSES, SignalAnalysisResult
from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.signal_analysis_command import SignalAnalysisCommand
from pandaplot.gui.components.common.busy_spinner import BusySpinner
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.models.events import DatasetOperationEvents, UIEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class SignalPanel(SidebarPanel):
    """Sidebar panel for signal analysis."""

    def __init__(
        self,
        app_context: AppContext,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(app_context=app_context, parent=parent)

        self.current_dataset: Optional[Dataset] = None
        self.current_dataset_id: Optional[str] = None

        self.last_result: Optional[SignalAnalysisResult] = None
        self._pending_command = None

        self._initialize()

    @override
    def _init_ui(self):
        self._init_panel_layout()

        self._set_title("📡 Signal Analysis")

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Analysis selector
        group = QGroupBox("Analysis")
        form = QFormLayout()

        self.analysis_combo = QComboBox()

        for analysis_type, info in SIGNAL_ANALYSES.items():
            self.analysis_combo.addItem(
                info.label,
                analysis_type,
            )

        self.analysis_combo.currentIndexChanged.connect(
            self._on_analysis_changed
        )

        form.addRow("Method:", self.analysis_combo)

        self.description_label = QLabel()
        self.description_label.setWordWrap(True)

        form.addRow("", self.description_label)

        group.setLayout(form)
        layout.addWidget(group)

        # Input
        self.input_group = QGroupBox("Input")
        self.input_layout = QFormLayout()
        self.input_group.setLayout(self.input_layout)

        layout.addWidget(self.input_group)

        self.column_combo = QComboBox()
        self.input_layout.addRow(
            "Signal column:",
            self.column_combo
        )

        # Parameters
        self.parameters_group = QGroupBox("Parameters")
        self.parameters_layout = QFormLayout()
        self.parameters_group.setLayout(self.parameters_layout)

        layout.addWidget(self.parameters_group)

        # Results
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout()

        self.run_btn = PButton("Run", role="secondary", on_click=self.run_analysis)

        results_layout.addWidget(self.run_btn)

        self.busy_spinner = BusySpinner()
        results_layout.addWidget(self.busy_spinner)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText("Run analysis to see results...")

        results_layout.addWidget(self.results_text)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        button_layout = QHBoxLayout()

        self.add_btn = PButton(
            "Add to Project", role="primary", on_click=self.add_results_to_project, enabled=False
        )

        self.clear_btn = PButton("Clear", role="secondary", on_click=self.clear)

        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.clear_btn)

        layout.addLayout(button_layout)

        layout.addStretch()

        self._set_content(content_widget, scrollable=True)
        self._on_analysis_changed()

    def _on_analysis_changed(self):
        analysis_type = self.analysis_combo.currentData()

        if analysis_type is None:
            return

        info = SIGNAL_ANALYSES[analysis_type]

        self.description_label.setText(
            info.description
        )

        self._build_parameter_widgets(info)
        self.clear()

    def _build_parameter_widgets(self, info):
        while self.parameters_layout.count():
            item = self.parameters_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # reset references
        self.sampling_rate = None
        self.nfft_spin = None
        self.window_combo = None
        self.nperseg_spin = None
        self.overlap_spin = None

        self.height_spin = None
        self.distance_spin = None
        self.prominence_spin = None
        self.threshold_spin = None

        # Sampling rate
        if info.uses_sampling_rate:
            self.sampling_rate = QDoubleSpinBox()
            self.sampling_rate.setRange(0.001, 1e9)
            self.sampling_rate.setValue(1000)

            self.parameters_layout.addRow(
                "Sampling rate:",
                self.sampling_rate
            )

        # FFT size
        if info.uses_nfft:
            self.nfft_spin = QSpinBox()
            self.nfft_spin.setRange(16, 1_000_000)
            self.nfft_spin.setValue(info.default_nfft)
            self.parameters_layout.addRow(
                "FFT size:",
                self.nfft_spin
            )

        # Window
        if info.uses_window:
            self.window_combo = QComboBox()

            self.window_combo.addItems(
                info.windows
            )

            self.parameters_layout.addRow(
                "Window:",
                self.window_combo
            )

        # STFT / PSD
        if info.uses_nperseg:
            self.nperseg_spin = QSpinBox()
            self.nperseg_spin.setRange(8, 1_000_000)
            self.nperseg_spin.setValue(
                info.default_nperseg
            )

            self.parameters_layout.addRow(
                "Segment size:",
                self.nperseg_spin
            )

        if info.uses_overlap:
            self.overlap_spin = QDoubleSpinBox()
            self.overlap_spin.setRange(0.0, 0.99)
            self.overlap_spin.setSingleStep(0.05)
            self.overlap_spin.setValue(
                info.default_overlap
            )

            self.parameters_layout.addRow(
                "Overlap:",
                self.overlap_spin
            )

        # Peak detection
        if info.uses_height:
            self.height_spin = QDoubleSpinBox()
            self.height_spin.setRange(
                -1e12,
                1e12
            )

            self.parameters_layout.addRow(
                "Minimum height:",
                self.height_spin
            )

        if info.uses_distance:
            self.distance_spin = QSpinBox()
            self.distance_spin.setRange(
                1,
                1_000_000
            )
            self.distance_spin.setValue(1)

            self.parameters_layout.addRow(
                "Minimum distance:",
                self.distance_spin
            )

        if info.uses_prominence:
            self.prominence_spin = QDoubleSpinBox()
            self.prominence_spin.setRange(
                0,
                1e12
            )

            self.parameters_layout.addRow(
                "Prominence:",
                self.prominence_spin
            )

        if info.uses_threshold:
            self.threshold_spin = QDoubleSpinBox()
            self.threshold_spin.setRange(
                -1e12,
                1e12
            )

            self.parameters_layout.addRow(
                "Threshold:",
                self.threshold_spin
            )

    def _numeric_columns(self) -> List[str]:
        if not self.current_dataset or self.current_dataset.data is None:
            return []

        import pandas as pd

        df = self.current_dataset.data

        return [
            str(c)
            for c in df.columns
            if pd.api.types.is_numeric_dtype(df[c])
        ]

    def _refresh_columns(self):
        self.column_combo.clear()
        self.column_combo.addItems(
            self._numeric_columns()
        )

        self.run_btn.setEnabled(
            self.column_combo.count() > 0
        )

    def on_tab_changed(self, event_data):
        if event_data.get("tab_type") == "dataset":

            dataset_id = event_data.get("tab_id")

            self.current_dataset_id = dataset_id
            self.current_dataset = None

            if dataset_id:
                project = (
                    self.app_context
                    .get_app_state()
                    .current_project
                )

                if project:
                    item = project.find_item(dataset_id)

                    if isinstance(item, Dataset):
                        self.current_dataset = item

            self._refresh_columns()

        else:
            self.current_dataset = None
            self.current_dataset_id = None
            self._refresh_columns()

    def on_columns_changed(self, event_data):
        if event_data.get("dataset_id") == self.current_dataset_id:
            self._refresh_columns()

    def _current_analysis_type(self):
        return self.analysis_combo.currentData()

    def _build_command(self):

        if not self.current_dataset_id:
            return None

        if not self.column_combo.currentText():
            return None

        parameters = {}

        if self.window_combo:
            parameters["window"] = self.window_combo.currentText()

        if self.nfft_spin:
            parameters["nfft"] = self.nfft_spin.value()

        if self.nperseg_spin:
            parameters["nperseg"] = self.nperseg_spin.value()

        if self.overlap_spin:
            parameters["overlap"] = self.overlap_spin.value()

        if self.height_spin:
            parameters["height"] = self.height_spin.value()

        if self.distance_spin:
            parameters["distance"] = self.distance_spin.value()

        if self.prominence_spin:
            parameters["prominence"] = self.prominence_spin.value()

        if self.threshold_spin:
            parameters["threshold"] = self.threshold_spin.value()

        return SignalAnalysisCommand(
            app_context=self.app_context,
            source_dataset_id=self.current_dataset_id,
            analysis_type=self._current_analysis_type(),
            column_name=self.column_combo.currentText(),
            sampling_rate=(
                self.sampling_rate.value()
                if self.sampling_rate
                else None
            ),
            parameters=parameters,
        )

    def run_analysis(self):
        # Run and "Add to Project" share one busy spinner and one
        # _pending_command slot -- letting both run at once would have
        # whichever finishes first stop the spinner and clear the other's
        # still-active reference out from under it, so treat them as mutually
        # exclusive rather than tracking two independent in-flight jobs.
        if self._pending_command is not None:
            return

        command = self._build_command()
        if command is None:
            return

        # Tab/column navigation stays enabled while a preview computes in
        # the background -- capture what was actually requested so a stale
        # completion (user switched dataset/column mid-flight) can be
        # discarded instead of overwriting whatever the panel now shows.
        dispatch_context = (self.current_dataset_id, self.column_combo.currentText())

        self.run_btn.setEnabled(False)
        self.add_btn.setEnabled(False)
        self.busy_spinner.start()
        self._pending_command = command  # keep alive until on_complete fires

        def _on_complete(result, error):
            self.busy_spinner.stop()
            self.run_btn.setEnabled(True)
            self._pending_command = None

            current_context = (self.current_dataset_id, self.column_combo.currentText())
            if current_context != dispatch_context:
                self.logger.info(
                    "Discarding stale signal analysis preview: dataset/column changed."
                )
                return

            if error is not None:
                self.last_result = None
                self.add_btn.setEnabled(False)
                self.results_text.setText(f"❌ Analysis failed:\n{error}")
                return

            self.last_result = result
            try:
                self.results_text.setText(self._format_result(result))
                self.add_btn.setEnabled(True)
            except Exception as e:
                self.last_result = None
                self.add_btn.setEnabled(False)
                self.results_text.setText(f"❌ Analysis failed:\n{e}")

        command.run_analysis_async(_on_complete)


    @staticmethod
    def _format_result(result):

        lines = [
            result.analysis_name,
            "=" * 30,
            "",
            f"Rows: {len(result.data)}",
            "",
            "Columns:"
        ]

        for col in result.data.columns:
            lines.append(f"- {col}")

        if result.metadata:
            lines.append("")
            lines.append("Parameters:")

            dominant = result.metadata.get("dominant_frequencies")

            for key, value in result.metadata.items():
                if key == "dominant_frequencies":
                    continue
                lines.append(f"{key}: {value}")

            if dominant:
                lines.append("")
                lines.append("Dominant frequencies:")

                for freq, amp in dominant:
                    lines.append(
                        f"- {freq:.2f} Hz (amplitude {amp:.3f})"
                    )

        return "\n".join(lines)

    def add_results_to_project(self):
        # See the matching guard/comment in run_analysis(): Run and Add
        # share one spinner and one _pending_command slot, so they must not
        # both be in flight at once.
        if self._pending_command is not None:
            return

        command = self._build_command()
        if command is None:
            return

        # See the matching capture/comment in run_analysis(): the commit
        # itself already happened for real (the dataset was created in the
        # project regardless of what the panel shows by the time it
        # completes), but the *display* of that outcome belongs to whatever
        # dataset/column is now selected -- skip it if that's changed.
        dispatch_context = (self.current_dataset_id, self.column_combo.currentText())

        self.run_btn.setEnabled(False)
        self.add_btn.setEnabled(False)
        self.busy_spinner.start()
        self._pending_command = command

        def _on_complete(result):
            self.busy_spinner.stop()
            self.run_btn.setEnabled(True)
            self._pending_command = None

            current_context = (self.current_dataset_id, self.column_combo.currentText())
            if current_context != dispatch_context:
                self.logger.info(
                    "Not displaying signal analysis commit result: dataset/column changed."
                )
                return

            if result is CommandResult.SUCCESS:
                self.last_result = command.result
                self.results_text.append("\n\n✅ Results added to project")
            else:
                self.add_btn.setEnabled(True)  # let the user retry

        command.on_complete = _on_complete
        executor = self.app_context.get_command_executor()
        if not executor.execute_command(command):
            # Synchronous validation failure -- on_complete never fires.
            self.busy_spinner.stop()
            self.run_btn.setEnabled(True)
            self.add_btn.setEnabled(True)
            self._pending_command = None

    def clear(self):
        if hasattr(self, "results_text"):
            self.results_text.clear()

        self.last_result = None
        if hasattr(self, "add_btn"):
            self.add_btn.setEnabled(False)
        if hasattr(self, "busy_spinner"):
            self.busy_spinner.stop()

    @override
    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        card_bg = palette.get("card_bg", "#ffffff")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#333333")

        self.setStyleSheet(f"""
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
                padding: 0 5px;
                background-color: {card_bg};
            }}
        """)

        self._apply_title_theme(base_fg, card_border)

        self.results_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {card_bg};
                color: {base_fg};
                border: 1px solid {card_border};
                border-radius: 4px;
            }}
        """)

    @override
    def setup_event_subscriptions(self):
        self.subscribe_to_multiple_events([
            (UIEvents.TAB_CHANGED, self.on_tab_changed),
            (
                DatasetOperationEvents.DATASET_COLUMN_ADDED,
                self.on_columns_changed
            ),
            (
                DatasetOperationEvents.DATASET_COLUMN_REMOVED,
                self.on_columns_changed
            ),
        ])