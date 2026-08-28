"""
Preprocessing panel for common data transformations (centering, standardizing,
scaling) applied to dataset columns before plotting or analysis.
"""

from typing import Any, Dict, Optional, override

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

from pandaplot.analysis import PreprocessingEngine, PreprocessingMethod
from pandaplot.analysis.preprocessing_types import PREPROCESSING_METHODS, list_methods
from pandaplot.commands.project.dataset.preprocess_column_command import (
    PreprocessColumnCommand,
)
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.models.events import DatasetEvents, DatasetOperationEvents, UIEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class PreprocessingPanel(SidebarPanel):
    """
    Side panel for applying preprocessing transformations to dataset columns.
    """

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.current_dataset: Optional[Dataset] = None
        self.current_dataset_id: Optional[str] = None

        self._initialize()
        self.setup_connections()
        self.on_method_changed()

    @override
    def _init_ui(self):
        """Build the panel layout."""
        self._init_panel_layout()

        self._set_title("⚖️ Preprocessing")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(6)

        self.create_method_section(content_layout)
        self.create_column_selection_section(content_layout)
        self.create_parameters_section(content_layout)
        self.create_result_section(content_layout)
        self.create_preview_section(content_layout)
        self.create_action_buttons(content_layout)

        content_layout.addStretch()

        self._set_content(content_widget, scrollable=True)

    def create_method_section(self, layout):
        """Create the transformation selector and its description."""
        group = QGroupBox("Transformation")
        group_layout = QVBoxLayout()

        form = QFormLayout()
        self.method_combo = QComboBox()
        for info in list_methods():
            self.method_combo.addItem(info.label, info.method.value)
        form.addRow("Method:", self.method_combo)
        group_layout.addLayout(form)

        self.description_label = QLabel("")
        self.description_label.setWordWrap(True)
        group_layout.addWidget(self.description_label)

        self.formula_label = QLabel("")
        self.formula_label.setWordWrap(True)
        group_layout.addWidget(self.formula_label)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def create_column_selection_section(self, layout):
        """Create the (multi-select) source column list."""
        group = QGroupBox("Columns")
        group_layout = QVBoxLayout()

        self.column_list = QListWidget()
        self.column_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.column_list.setMaximumHeight(120)
        group_layout.addWidget(QLabel("Select one or more numeric columns:"))
        group_layout.addWidget(self.column_list)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def create_parameters_section(self, layout):
        """Create the method-specific parameters (min-max range)."""
        self.parameters_group = QGroupBox("Parameters")
        self.parameters_layout = QFormLayout()

        self.range_min_spin = QDoubleSpinBox()
        self.range_min_spin.setRange(-1_000_000.0, 1_000_000.0)
        self.range_min_spin.setDecimals(3)
        self.range_min_spin.setValue(0.0)

        self.range_max_spin = QDoubleSpinBox()
        self.range_max_spin.setRange(-1_000_000.0, 1_000_000.0)
        self.range_max_spin.setDecimals(3)
        self.range_max_spin.setValue(1.0)

        self.range_min_row_label = QLabel("Output min:")
        self.range_max_row_label = QLabel("Output max:")
        self.parameters_layout.addRow(self.range_min_row_label, self.range_min_spin)
        self.parameters_layout.addRow(self.range_max_row_label, self.range_max_spin)

        self.parameters_group.setLayout(self.parameters_layout)
        layout.addWidget(self.parameters_group)

    def create_result_section(self, layout):
        """Create result-naming options."""
        group = QGroupBox("Result")
        group_layout = QVBoxLayout()

        self.replace_check = QCheckBox("Replace source columns in place")
        group_layout.addWidget(self.replace_check)

        self.naming_hint = QLabel("")
        self.naming_hint.setWordWrap(True)
        group_layout.addWidget(self.naming_hint)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def create_preview_section(self, layout):
        """Create the preview area."""
        group = QGroupBox("Preview")
        group_layout = QVBoxLayout()

        self.preview_btn = PButton("Preview", role="secondary", on_click=self.preview)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(140)
        self.preview_text.setPlaceholderText("Preview results will appear here...")

        group_layout.addWidget(self.preview_btn)
        group_layout.addWidget(self.preview_text)
        group.setLayout(group_layout)
        layout.addWidget(group)

    def create_action_buttons(self, layout):
        """Create the apply/clear buttons."""
        button_layout = QHBoxLayout()

        self.apply_btn = PButton("Apply", role="primary", on_click=self.apply)

        self.clear_btn = PButton("Clear", role="secondary", on_click=self.clear_inputs)

        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)

    def setup_connections(self):
        """Wire up signal connections."""
        self.method_combo.currentIndexChanged.connect(self.on_method_changed)
        self.replace_check.toggled.connect(self.update_naming_hint)
        self.column_list.itemSelectionChanged.connect(self.update_naming_hint)

    # -- state helpers ----------------------------------------------------

    def selected_method(self) -> PreprocessingMethod:
        """Return the currently selected preprocessing method."""
        return PreprocessingMethod(self.method_combo.currentData())

    def selected_columns(self) -> list[str]:
        """Return the currently selected column names."""
        return [item.text() for item in self.column_list.selectedItems()]

    def on_method_changed(self):
        """Update description, formula and parameter visibility for the method."""
        info = PREPROCESSING_METHODS[self.selected_method()]
        self.description_label.setText(info.description)
        self.formula_label.setText(f"Formula:  {info.formula}")

        show_range = info.uses_feature_range
        self.range_min_row_label.setVisible(show_range)
        self.range_min_spin.setVisible(show_range)
        self.range_max_row_label.setVisible(show_range)
        self.range_max_spin.setVisible(show_range)
        self.parameters_group.setVisible(show_range)
        if show_range:
            self.range_min_spin.setValue(info.default_range_min)
            self.range_max_spin.setValue(info.default_range_max)

        self.update_naming_hint()

    def update_naming_hint(self):
        """Show the user what result columns will be produced."""
        info = PREPROCESSING_METHODS[self.selected_method()]
        columns = self.selected_columns()
        if not columns:
            self.naming_hint.setText("No columns selected.")
            return
        if self.replace_check.isChecked():
            self.naming_hint.setText("Selected columns will be overwritten in place.")
        else:
            examples = ", ".join(f"{c}_{info.suffix}" for c in columns[:3])
            more = "" if len(columns) <= 3 else ", ..."
            self.naming_hint.setText(f"New columns: {examples}{more}")

    def _get_params(self) -> Dict[str, Any]:
        """Collect method-specific parameters from the UI."""
        info = PREPROCESSING_METHODS[self.selected_method()]
        params: Dict[str, Any] = {}
        if info.uses_feature_range:
            params["range_min"] = self.range_min_spin.value()
            params["range_max"] = self.range_max_spin.value()
        return params

    def _get_config(self) -> Dict[str, Any]:
        """Build the command configuration from the current UI state."""
        return {
            "method": self.selected_method().value,
            "source_columns": self.selected_columns(),
            "params": self._get_params(),
            "replace_existing": self.replace_check.isChecked(),
        }

    def validate_inputs(self) -> bool:
        """Validate that inputs are ready to apply/preview."""
        if self.current_dataset is None or self.current_dataset.data is None:
            self.preview_text.setText("❌ No dataset selected.")
            return False
        if not self.selected_columns():
            self.preview_text.setText("❌ Please select at least one column.")
            return False
        info = PREPROCESSING_METHODS[self.selected_method()]
        if info.uses_feature_range and self.range_max_spin.value() <= self.range_min_spin.value():
            self.preview_text.setText("❌ Output max must be greater than output min.")
            return False
        return True

    # -- actions ----------------------------------------------------------

    def preview(self):
        """Preview the transformation on the first selected column."""
        try:
            if not self.validate_inputs():
                return
            assert self.current_dataset is not None and self.current_dataset.data is not None

            df = self.current_dataset.data
            method = self.selected_method()
            params = self._get_params()
            column = self.selected_columns()[0]

            result = PreprocessingEngine.transform(method, df[column], params)

            lines = [
                f"Method: {PREPROCESSING_METHODS[method].label}",
                f"Column: {column}",
                "",
                "Fitted parameters:",
            ]
            for key, value in result.statistics.items():
                lines.append(f"  {key}: {value:.6g}")

            lines.append("")
            lines.append("First values (original → transformed):")
            original = df[column].head(5)
            transformed = result.data.head(5)
            for orig, trans in zip(original.tolist(), transformed.tolist(), strict=False):
                orig_str = f"{orig:.4g}" if isinstance(orig, (int, float)) else str(orig)
                trans_str = f"{trans:.4g}" if isinstance(trans, (int, float)) else str(trans)
                lines.append(f"  {orig_str} → {trans_str}")

            if len(self.selected_columns()) > 1:
                lines.append("")
                lines.append(
                    f"(+{len(self.selected_columns()) - 1} more column(s) will be transformed the same way)"
                )

            self.preview_text.setText("\n".join(lines))
        except Exception as e:
            self.preview_text.setText(f"❌ Preview error: {e}")

    def apply(self):
        """Apply the transformation through the command system."""
        try:
            if not self.validate_inputs():
                return
            if not self.current_dataset_id:
                self.preview_text.setText("❌ No dataset selected.")
                return

            config = self._get_config()
            command = PreprocessColumnCommand(
                self.app_context, self.current_dataset_id, config
            )
            success = self.app_context.get_command_executor().execute_command(command)

            if success:
                # The command emits the structured column-added / data-changed
                # events that refresh the data tab and column-source selectors.
                count = len(config["source_columns"])
                self.preview_text.setText(
                    f"✅ Preprocessing applied to {count} column(s)."
                )
            else:
                self.preview_text.setText(
                    "❌ Failed to apply. Check that the columns are numeric."
                )
        except Exception as e:
            self.preview_text.setText(f"❌ Error applying preprocessing: {e}")

    def clear_inputs(self):
        """Reset the panel to its default state."""
        self.column_list.clearSelection()
        self.replace_check.setChecked(False)
        self.method_combo.setCurrentIndex(0)
        self.preview_text.clear()
        self.on_method_changed()

    # -- dataset context --------------------------------------------------

    def update_column_choices(self):
        """Repopulate the column list from the current dataset."""
        self.column_list.clear()
        if self.current_dataset is None or self.current_dataset.data is None:
            return
        self.column_list.addItems(list(self.current_dataset.data.columns))
        self.update_naming_hint()

    @override
    def setup_event_subscriptions(self):
        """Subscribe to dataset and tab events."""
        self.subscribe_to_multiple_events([
            (DatasetEvents.DATASET_CHANGED, self.on_dataset_changed),
            (DatasetOperationEvents.DATASET_COLUMN_ADDED, self.on_columns_changed),
            (DatasetOperationEvents.DATASET_COLUMN_REMOVED, self.on_columns_changed),
            (UIEvents.TAB_CHANGED, self.on_tab_changed),
        ])

    def on_dataset_changed(self, event_data):
        """Handle dataset content changes."""
        if event_data.get("dataset_id") == self.current_dataset_id:
            self.update_column_choices()

    def on_columns_changed(self, event_data):
        """Handle column additions/removals."""
        if event_data.get("dataset_id") == self.current_dataset_id:
            self.update_column_choices()

    def on_tab_changed(self, event_data):
        """Handle tab changes to track the active dataset."""
        if event_data.get("tab_type") == "dataset":
            dataset_id = event_data.get("tab_id")
            self.current_dataset_id = dataset_id
            project = self.app_context.get_app_state().current_project
            dataset = project.find_item(dataset_id) if project and dataset_id else None
            self.current_dataset = dataset if isinstance(dataset, Dataset) else None
        else:
            self.current_dataset = None
            self.current_dataset_id = None
        self.update_column_choices()

    @override
    def _apply_theme(self):
        """Apply the current theme to the panel."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        card_bg = palette.get("card_bg", "#ffffff")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#333333")
        secondary_fg = palette.get("secondary_fg", "#666666")

        self.setStyleSheet(f"""
            PreprocessingPanel {{
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

        for label in (self.description_label, self.naming_hint):
            label.setStyleSheet(f"QLabel {{ color: {secondary_fg}; background-color: transparent; }}")
        self.formula_label.setStyleSheet(
            f"QLabel {{ color: {base_fg}; font-family: monospace; background-color: transparent; }}"
        )
