"""
Descriptive statistics panel: a guided side panel for computing summary
statistics (mean, standard deviation, quartiles, etc.) for dataset columns,
previewing a report, and adding the results to the project as data.
"""

from typing import List, Optional, override

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pandaplot.analysis import DescriptiveStatsResult
from pandaplot.commands.project.dataset.descriptive_stats_command import DescriptiveStatsCommand
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.models.events import DatasetEvents, DatasetOperationEvents, UIEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class DescriptiveStatsPanel(SidebarPanel):
    """Side panel for computing descriptive statistics on dataset columns."""

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.current_dataset: Optional[Dataset] = None
        self.current_dataset_id: Optional[str] = None
        self.last_result: Optional[DescriptiveStatsResult] = None

        self._initialize()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    @override
    def _init_ui(self):
        self._init_panel_layout()

        self._set_title("📋 Descriptive Statistics")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(6)

        self._create_input_section(content_layout)
        self._create_options_section(content_layout)
        self._create_results_section(content_layout)
        self._create_action_buttons(content_layout)

        content_layout.addStretch()
        self._set_content(content_widget, scrollable=True)

    def _create_input_section(self, layout):
        group = QGroupBox("Columns")
        group_layout = QVBoxLayout()

        self.column_list = QListWidget()
        self.column_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.column_list.setMaximumHeight(160)
        group_layout.addWidget(self.column_list)

        hint = QLabel("Select one or more numeric columns (Ctrl/Shift-click).")
        hint.setWordWrap(True)
        self._apply_hint_label_theme(hint)
        group_layout.addWidget(hint)

        self.select_all_btn = PButton(
            "Select all", role="secondary", on_click=self.column_list.selectAll
        )
        group_layout.addWidget(self.select_all_btn)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def _create_options_section(self, layout):
        group = QGroupBox("Options")
        group_layout = QVBoxLayout()

        digits_row = QHBoxLayout()
        digits_row.addWidget(QLabel("Significant digits:"))
        self.digits_spin = QSpinBox()
        self.digits_spin.setRange(1, 12)
        self.digits_spin.setValue(6)
        digits_row.addWidget(self.digits_spin)
        digits_row.addStretch()
        group_layout.addLayout(digits_row)

        self.report_check = QCheckBox("Also add a written report (note)")
        self.report_check.setChecked(True)
        group_layout.addWidget(self.report_check)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def _create_results_section(self, layout):
        group = QGroupBox("Results")
        group_layout = QVBoxLayout()

        self.run_btn = PButton("Compute", role="secondary", on_click=self.compute)
        group_layout.addWidget(self.run_btn)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(180)
        self.results_text.setPlaceholderText("Compute statistics to see a preview here...")
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
    # Actions
    # ------------------------------------------------------------------

    def _selected_columns(self) -> List[str]:
        return [item.text() for item in self.column_list.selectedItems()]

    def _build_command(self) -> Optional[DescriptiveStatsCommand]:
        if not self.current_dataset_id:
            self.results_text.setText("❌ No dataset selected.")
            return None

        columns = self._selected_columns()
        if not columns:
            self.results_text.setText("❌ Please select at least one column.")
            return None

        return DescriptiveStatsCommand(
            app_context=self.app_context,
            source_dataset_id=self.current_dataset_id,
            column_names=columns,
            digits=self.digits_spin.value(),
            include_report=self.report_check.isChecked(),
        )

    def compute(self):
        """Compute statistics and preview them (without adding to the project)."""
        command = self._build_command()
        if command is None:
            return
        try:
            result = command.compute()
        except Exception as e:
            self.last_result = None
            self.add_btn.setEnabled(False)
            self.results_text.setText(f"❌ Computation failed: {e}")
            return

        self.last_result = result
        self.add_btn.setEnabled(True)
        self.results_text.setPlainText(result.report())

    def add_results_to_project(self):
        """Run the command through the executor, adding a dataset (+ report note)."""
        command = self._build_command()
        if command is None:
            return
        executed = self.app_context.get_command_executor().execute_command(command)
        if executed and command.result_dataset_id:
            self.last_result = command.result
            self.publish_event(DatasetEvents.DATASET_CREATED, {
                "dataset_id": command.result_dataset_id,
                "source": "descriptive_stats_panel",
            })
            name = command.result.result_name() if command.result else "results"
            report = command.result.report() if command.result else ""
            self.results_text.setPlainText(
                f"✅ Results added to project as dataset:\n'{name}'\n\n{report}"
            )
        else:
            self.results_text.setText("❌ Failed to add results. Please check your selection.")

    def clear(self):
        self.results_text.clear()
        self.last_result = None
        self.add_btn.setEnabled(False)

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
        """Rebuild the column list against the current dataset's columns."""
        selected = set(self._selected_columns())
        self.column_list.clear()
        columns = self._numeric_columns()
        self.column_list.addItems(columns)
        # Preserve selection where possible; otherwise select all as a default.
        if selected:
            for i in range(self.column_list.count()):
                item = self.column_list.item(i)
                if item.text() in selected:
                    item.setSelected(True)
        else:
            self.column_list.selectAll()

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
            DescriptiveStatsPanel {{
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
