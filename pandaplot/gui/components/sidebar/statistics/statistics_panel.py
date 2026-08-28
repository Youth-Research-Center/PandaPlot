"""
Statistics panel: a guided side panel for running the most common statistical
hypothesis tests on dataset columns and adding the results to the project as data.
"""

from typing import List, Optional, override

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pandaplot.analysis import STAT_TESTS, InputMode, StatTestResult, StatTestType
from pandaplot.commands.project.dataset.statistical_test_command import StatisticalTestCommand
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.gui.components.sidebar.statistics.test_info_dialog import InfoDialogHelper
from pandaplot.models.events import DatasetEvents, DatasetOperationEvents, UIEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class StatisticsPanel(SidebarPanel):
    """Side panel for guided statistical testing on dataset columns."""

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.current_dataset: Optional[Dataset] = None
        self.current_dataset_id: Optional[str] = None
        self.last_result: Optional[StatTestResult] = None

        self._initialize()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    @override
    def _init_ui(self):
        self._init_panel_layout()

        self._set_title("🧪 Statistical Tests")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(6)

        self._create_test_type_section(content_layout)
        self._create_input_section(content_layout)
        self._create_parameters_section(content_layout)
        self._create_results_section(content_layout)
        self._create_action_buttons(content_layout)

        content_layout.addStretch()
        self._set_content(content_widget, scrollable=True)

        # Populate for the initially selected test.
        self._on_test_type_changed()

    def _create_test_type_section(self, layout):
        group = QGroupBox("Test")
        group_layout = QVBoxLayout()

        form = QFormLayout()
        self.test_type_combo = QComboBox()
        for test_type, info in STAT_TESTS.items():
            self.test_type_combo.addItem(info.label, test_type)
        self.test_type_combo.currentIndexChanged.connect(self._on_test_type_changed)

        # Combo + an info button that opens a learner-friendly explanation.
        selector_row = QHBoxLayout()
        selector_row.setContentsMargins(0, 0, 0, 0)
        selector_row.addWidget(self.test_type_combo, 1)
        self.info_btn = PButton("ℹ️", role="secondary", icon=True, on_click=self._show_test_info)
        self.info_btn.setFixedWidth(32)
        self.info_btn.setToolTip("Learn about this test: explanation, formula and an example")
        selector_row.addWidget(self.info_btn)
        form.addRow("Test:", selector_row)
        group_layout.addLayout(form)

        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        group_layout.addWidget(self.description_label)

        self.assumptions_label = QLabel()
        self.assumptions_label.setWordWrap(True)
        group_layout.addWidget(self.assumptions_label)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def _create_input_section(self, layout):
        self.input_group = QGroupBox("Data Selection")
        self.input_layout = QFormLayout()
        self.input_group.setLayout(self.input_layout)
        layout.addWidget(self.input_group)

    def _create_parameters_section(self, layout):
        self.parameters_group = QGroupBox("Parameters")
        self.parameters_layout = QFormLayout()
        self.parameters_group.setLayout(self.parameters_layout)
        layout.addWidget(self.parameters_group)

    def _create_results_section(self, layout):
        group = QGroupBox("Results")
        group_layout = QVBoxLayout()

        self.run_btn = PButton("Run", role="secondary", on_click=self.run_test)
        group_layout.addWidget(self.run_btn)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(160)
        self.results_text.setPlaceholderText("Run a test to see results here...")
        group_layout.addWidget(self.results_text)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def _create_action_buttons(self, layout):
        button_layout = QHBoxLayout()

        self.add_btn = PButton(
            "Add to Project", role="primary", on_click=self.add_results_to_project, enabled=False
        )

        self.clear_btn = PButton("Clear", role="secondary", on_click=self.clear)

        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)

    # ------------------------------------------------------------------
    # Dynamic form building
    # ------------------------------------------------------------------

    def _current_test_type(self) -> StatTestType:
        return self.test_type_combo.currentData()

    def _show_test_info(self):
        """Open the educational dialog for the currently selected test."""
        test_type = self._current_test_type()
        if test_type is None:
            return
        dialog = InfoDialogHelper(self.app_context, STAT_TESTS[test_type], parent=self)
        dialog.exec()

    def _on_test_type_changed(self):
        test_type = self._current_test_type()
        if test_type is None:
            return
        info = STAT_TESTS[test_type]

        self.description_label.setText(f"ℹ️ {info.description}")
        self.assumptions_label.setText(f"Assumptions: {info.assumptions}" if info.assumptions else "")
        self._apply_hint_label_theme(self.description_label)
        self._apply_hint_label_theme(self.assumptions_label)

        self._build_input_widgets(info.input_mode)
        self._build_parameter_widgets(info)

        # Selecting a new test invalidates the previous result.
        self.last_result = None
        self.add_btn.setEnabled(False)

    def _build_input_widgets(self, input_mode: InputMode):
        self._clear_layout(self.input_layout)
        self.column_combos: List[QComboBox] = []
        self.group_list: Optional[QListWidget] = None

        columns = self._numeric_columns()

        if input_mode == InputMode.ONE:
            combo = QComboBox()
            combo.addItems(columns)
            self.column_combos.append(combo)
            self.input_layout.addRow("Sample column:", combo)

        elif input_mode == InputMode.TWO:
            combo_a = QComboBox()
            combo_b = QComboBox()
            combo_a.addItems(columns)
            combo_b.addItems(columns)
            if len(columns) >= 2:
                combo_b.setCurrentIndex(1)
            self.column_combos.extend([combo_a, combo_b])
            self.input_layout.addRow("Column A:", combo_a)
            self.input_layout.addRow("Column B:", combo_b)

        else:  # MANY
            self.group_list = QListWidget()
            self.group_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.group_list.addItems(columns)
            self.group_list.setMaximumHeight(140)
            # Preselect first two groups as a convenience.
            for i in range(min(2, len(columns))):
                self.group_list.item(i).setSelected(True)
            hint = QLabel("Select 2+ numeric group columns (Ctrl/Shift-click).")
            self._apply_hint_label_theme(hint)
            self.input_layout.addRow("Groups:", self.group_list)
            self.input_layout.addRow("", hint)

    def _build_parameter_widgets(self, info):
        self._clear_layout(self.parameters_layout)

        # Significance level is common to every test.
        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setDecimals(4)
        self.alpha_spin.setRange(0.0001, 0.5)
        self.alpha_spin.setSingleStep(0.01)
        self.alpha_spin.setValue(0.05)
        self.parameters_layout.addRow("Significance (α):", self.alpha_spin)

        self.popmean_spin = None
        if info.uses_popmean:
            self.popmean_spin = QDoubleSpinBox()
            self.popmean_spin.setDecimals(6)
            self.popmean_spin.setRange(-1e12, 1e12)
            self.popmean_spin.setValue(0.0)
            self.parameters_layout.addRow("Expected mean (μ₀):", self.popmean_spin)

        self.alternative_combo = None
        if info.uses_alternative:
            self.alternative_combo = QComboBox()
            self.alternative_combo.addItems(["two-sided", "less", "greater"])
            self.parameters_layout.addRow("Alternative:", self.alternative_combo)

        self.equal_var_check = None
        if info.uses_equal_var:
            self.equal_var_check = QCheckBox("Assume equal variance (uncheck for Welch)")
            self.equal_var_check.setChecked(True)
            self.parameters_layout.addRow("", self.equal_var_check)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _selected_columns(self) -> List[str]:
        info = STAT_TESTS[self._current_test_type()]
        if info.input_mode == InputMode.MANY:
            if self.group_list is None:
                return []
            return [item.text() for item in self.group_list.selectedItems()]
        return [combo.currentText() for combo in self.column_combos if combo.currentText()]

    def _build_command(self) -> Optional[StatisticalTestCommand]:
        if not self.current_dataset_id:
            self.results_text.setText("❌ No dataset selected.")
            return None

        test_type = self._current_test_type()
        info = STAT_TESTS[test_type]
        columns = self._selected_columns()

        if info.input_mode == InputMode.MANY and len(columns) < 2:
            self.results_text.setText("❌ Please select at least 2 group columns.")
            return None
        if info.input_mode == InputMode.TWO and (len(columns) < 2 or columns[0] == columns[1]):
            self.results_text.setText("❌ Please select two different columns.")
            return None
        if info.input_mode == InputMode.ONE and not columns:
            self.results_text.setText("❌ Please select a column.")
            return None

        return StatisticalTestCommand(
            app_context=self.app_context,
            source_dataset_id=self.current_dataset_id,
            test_type=test_type,
            column_names=columns,
            alpha=self.alpha_spin.value(),
            alternative=self.alternative_combo.currentText() if self.alternative_combo else "two-sided",
            popmean=self.popmean_spin.value() if self.popmean_spin else 0.0,
            equal_var=self.equal_var_check.isChecked() if self.equal_var_check else True,
        )

    def run_test(self):
        """Run the selected test and preview results (without adding to project)."""
        command = self._build_command()
        if command is None:
            return
        try:
            result = command.run_test()
        except Exception as e:
            self.last_result = None
            self.add_btn.setEnabled(False)
            self.results_text.setText(f"❌ Test failed: {e}")
            return

        self.last_result = result
        self.add_btn.setEnabled(True)
        self.results_text.setText(self._format_result(result))

    def add_results_to_project(self):
        """Run the test through the command executor and add results as a dataset."""
        command = self._build_command()
        if command is None:
            return
        executed = self.app_context.get_command_executor().execute_command(command)
        if executed and command.result_dataset_id:
            self.last_result = command.result
            self.publish_event(DatasetEvents.DATASET_CREATED, {
                "dataset_id": command.result_dataset_id,
                "source": "statistics_panel",
            })
            name = command.result.result_name() if command.result else "results"
            self.results_text.setText(
                f"✅ Results added to project as dataset:\n'{name}'\n\n"
                + (self._format_result(command.result) if command.result else "")
            )
        else:
            self.results_text.setText("❌ Failed to add results. Please check your selection.")

    def clear(self):
        self.results_text.clear()
        self.last_result = None
        self.add_btn.setEnabled(False)

    @staticmethod
    def _format_result(result: StatTestResult) -> str:
        lines = [f"{result.test_name}", "=" * 32]
        for metric, value in result.rows:
            if metric == "Conclusion":
                continue
            lines.append(f"{metric}: {value}")
        if result.conclusion:
            lines.append("")
            lines.append(result.conclusion)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Dataset context handling
    # ------------------------------------------------------------------

    def _numeric_columns(self) -> List[str]:
        if not self.current_dataset or self.current_dataset.data is None:
            return []
        import pandas as pd

        df = self.current_dataset.data
        return [str(c) for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

    def _refresh_inputs(self):
        """Rebuild the input widgets against the current dataset's columns."""
        test_type = self._current_test_type()
        if test_type is not None:
            self._build_input_widgets(STAT_TESTS[test_type].input_mode)

    def update_context(self, tab_widget):
        """Update panel context from the active tab (called by sidebar wiring)."""
        if tab_widget is not None and getattr(tab_widget, "dataset", None):
            self.current_dataset = tab_widget.dataset
            self.current_dataset_id = tab_widget.dataset.id
            self.setEnabled(True)
            self._refresh_inputs()
        else:
            self.current_dataset = None
            self.current_dataset_id = None
            self.setEnabled(False)

    @override
    def setup_event_subscriptions(self):
        self.subscribe_to_multiple_events([
            (UIEvents.TAB_CHANGED, self.on_tab_changed),
            (DatasetOperationEvents.DATASET_COLUMN_ADDED, self.on_columns_changed),
            (DatasetOperationEvents.DATASET_COLUMN_REMOVED, self.on_columns_changed),
        ])

    def on_tab_changed(self, event_data):
        if event_data.get("tab_type") == "dataset":
            dataset_id = event_data.get("tab_id")
            self.current_dataset_id = dataset_id
            self.current_dataset = None
            if dataset_id:
                project = self.app_context.get_app_state().current_project
                if project:
                    item = project.find_item(dataset_id)
                    if isinstance(item, Dataset):
                        self.current_dataset = item
            self._refresh_inputs()
        else:
            self.current_dataset = None
            self.current_dataset_id = None
            self._refresh_inputs()

    def on_columns_changed(self, event_data):
        if event_data.get("dataset_id") == self.current_dataset_id:
            self._refresh_inputs()

    # ------------------------------------------------------------------
    # Helpers / theming
    # ------------------------------------------------------------------

    @staticmethod
    def _clear_layout(layout: QFormLayout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _apply_hint_label_theme(self, label: QLabel):
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        secondary_fg = palette.get("secondary_fg", "#666666")
        label.setStyleSheet(f"QLabel {{ color: {secondary_fg}; font-style: italic; background-color: transparent; }}")

    @override
    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        card_bg = palette.get("card_bg", "#ffffff")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#333333")

        self.setStyleSheet(f"""
            StatisticsPanel {{
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
