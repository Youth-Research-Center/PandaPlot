"""
Transform panel for data transformations in the sidebar.

Adapted from transform_tab.py to provide a compact sidebar interface
for applying transformations to dataset tabs.
"""

from typing import Optional, override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.gui.components.sidebar.transform.transform_controller import TransformController
from pandaplot.models.events import DatasetOperationEvents, UIEvents
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class TransformPanel(SidebarPanel):
    """
    Transform panel for data transformations, adapted from transform_tab.py.
    Designed for sidebar integration with conditional visibility.
    """

    def __init__(self, app_context: AppContext, parent: Optional[QWidget]=None):
        super().__init__(app_context=app_context, parent=parent)
        self.current_dataset_tab = None
        self.current_dataset = None
        self._last_transform_error: Optional[str] = None

        # Initialize transform controller
        self.transform_controller = TransformController(app_context)
        
        # Transform state
        self.available_columns = []
        self.transform_types = [
            "Custom Function",
            "Math Operations", 
            "String Operations",
            "Date/Time Operations",
            "Statistical Operations"
        ]

        self._initialize()
        self.setup_connections()

    @override
    def _init_ui(self):
        """Create the UI layout optimized for sidebar width constraints."""
        # Main layout with scroll area for long content
        self._init_panel_layout()

        # Panel title
        self._set_title("🔧 Transform Operations")

        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(6)

        # Header section (dataset info)
        self.create_header_section(content_layout)

        # Transform type selection
        self.create_transform_type_section(content_layout)

        # Column selection section
        self.create_column_selection_section(content_layout)

        # Function definition area
        self.create_function_section(content_layout)

        # Preview section
        self.create_preview_section(content_layout)

        # Action buttons
        self.create_action_buttons(content_layout)

        # Add stretch to push content to top
        content_layout.addStretch()

        # Set content widget in scroll area
        self._set_content(content_widget, scrollable=True)
    
    @override
    def _apply_theme(self):
        """Apply current theme to transform panel components."""
        # Get theme colors
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        
        card_bg = palette.get("card_bg", "#ffffff")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#333333")
        secondary_fg = palette.get("secondary_fg", "#666666")

        # Apply theme to main widget (like project view panel)
        self.setStyleSheet(f"""
            TransformPanel {{
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
        
        # Style panel title
        self.title_label.setStyleSheet(self.title_stylesheet(base_fg, card_border))
        
        # Style dataset labels in header
        self.dataset_label.setStyleSheet(f"""
            QLabel {{
                font-weight: bold;
                color: {base_fg};
                background-color: transparent;
            }}
        """)
        
        self.row_count_label.setStyleSheet(f"""
            QLabel {{
                color: {secondary_fg};
                font-size: 10px;
                background-color: transparent;
            }}
        """)
        
        # Style preview text area
        self.preview_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
                font-family: monospace;
                color: {base_fg};
                padding: 4px;
            }}
        """)
        
    def create_header_section(self, layout):
        """Create header section showing current dataset info."""
        header_group = QGroupBox("Active Dataset")
        header_layout = QVBoxLayout(header_group)
        
        self.dataset_label = QLabel("No dataset selected")
        self.dataset_label.setWordWrap(True)
        # Remove hardcoded styling - will be applied in _apply_theme
        
        self.row_count_label = QLabel("")
        # Remove hardcoded styling - will be applied in _apply_theme
        
        header_layout.addWidget(self.dataset_label)
        header_layout.addWidget(self.row_count_label)
        
        layout.addWidget(header_group)
    
    def create_transform_type_section(self, layout):
        """Create transform type selection section."""
        type_group = QGroupBox("Transform Type")
        type_layout = QFormLayout(type_group)
        
        self.transform_type_combo = QComboBox()
        self.transform_type_combo.addItems(self.transform_types)
        self.transform_type_combo.setCurrentText("Custom Function")
        
        type_layout.addRow("Type:", self.transform_type_combo)
        layout.addWidget(type_group)
    
    def create_column_selection_section(self, layout):
        """Create column selection section."""
        column_group = QGroupBox("Column Selection")
        column_layout = QVBoxLayout(column_group)
        
        # Source columns
        form_layout = QFormLayout()
        
        # Use QListWidget for multiple selection instead of QComboBox
        self.source_column_list = QListWidget()
        self.source_column_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.source_column_list.setMaximumHeight(80)  # Compact height for sidebar
        form_layout.addRow("Source Columns:", self.source_column_list)
        
        # New column name
        self.new_column_name = QLineEdit()
        self.new_column_name.setPlaceholderText("new_column")
        form_layout.addRow("New Column:", self.new_column_name)
        
        # Option to replace existing column
        self.replace_column_check = QCheckBox("Replace existing column")
        
        column_layout.addLayout(form_layout)
        column_layout.addWidget(self.replace_column_check)
        
        layout.addWidget(column_group)
    
    def create_function_section(self, layout):
        """Create function definition section."""
        function_group = QGroupBox("Transform Function")
        function_layout = QVBoxLayout(function_group)

        # Toolbar: insert a ready-made function, or browse available functions.
        toolbar_layout = QHBoxLayout()

        self.insert_function_btn = QToolButton()
        self.insert_function_btn.setText("ƒ  Insert function ▾")
        self.insert_function_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.insert_function_btn.setMenu(self._build_function_menu())

        self.reference_btn = QToolButton()
        self.reference_btn.setText("?")
        self.reference_btn.setToolTip("Show the variables and functions you can use")
        self.reference_btn.clicked.connect(self.toggle_function_reference)

        toolbar_layout.addWidget(self.insert_function_btn)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.reference_btn)
        function_layout.addLayout(toolbar_layout)

        # Function input area (compact for sidebar)
        self.function_text = QTextEdit()
        self.function_text.setMaximumHeight(100)  # Keep compact
        self.function_text.setPlaceholderText(
            "Use 'x' for the selected column, e.g.\n"
            "  x * 2            (double the values)\n"
            "  (x - x.mean()) / x.std()   (z-score)\n"
            "  np.sqrt(x)       (square root)\n"
            "Or pick one from 'Insert function ▾' above."
        )
        function_layout.addWidget(self.function_text)

        # Collapsible reference of usable variables and functions (hidden by default).
        self.function_reference = QLabel(self._function_reference_text())
        self.function_reference.setWordWrap(True)
        self.function_reference.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.function_reference.setVisible(False)
        function_layout.addWidget(self.function_reference)

        layout.addWidget(function_group)

    def _build_function_menu(self) -> "QMenu":
        """Build a categorized menu of ready-made transformation functions."""
        menu = QMenu(self)
        templates = self.transform_controller.get_transformation_templates()
        for category, entries in templates.items():
            submenu = menu.addMenu(category)
            for entry in entries:
                action = submenu.addAction(entry["name"])
                action.setToolTip(f"{entry['description']}  →  {entry['code']}")
                # Bind the code for this entry via a default argument.
                action.triggered.connect(
                    lambda _checked=False, code=entry["code"]: self.insert_function_code(code)
                )
        # Surface tooltips inside the menu.
        menu.setToolTipsVisible(True)
        return menu

    def _function_reference_text(self) -> str:
        """Human-readable list of the variables and functions available."""
        return (
            "<b>Variables</b>: <code>x</code> (also <code>value</code>, "
            "<code>column</code>, <code>data</code>) = the selected column.<br>"
            "<b>Math</b>: <code>np.sqrt</code>, <code>np.log</code>, "
            "<code>np.log10</code>, <code>np.exp</code>, <code>np.abs</code>, "
            "<code>np.sin/cos/tan</code>, <code>np.sign</code>.<br>"
            "<b>Stats</b>: <code>x.mean()</code>, <code>x.std()</code>, "
            "<code>x.median()</code>, <code>x.min()</code>, <code>x.max()</code>, "
            "<code>x.rank()</code>, <code>x.cumsum()</code>, "
            "<code>x.rolling(n).mean()</code>, <code>x.shift(1)</code>.<br>"
            "<b>Text</b>: <code>x.str.upper()</code>, <code>x.str.lower()</code>, "
            "<code>x.str.strip()</code>, <code>x.str.len()</code>.<br>"
            "<b>Date/Time</b>: <code>pd.to_datetime(x)</code>, "
            "<code>pd.to_datetime(x).dt.year</code>."
        )

    def create_preview_section(self, layout):
        """Create compact preview section."""
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        # Preview text area (compact)
        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(80)
        self.preview_text.setReadOnly(True)
        # Remove hardcoded styling - will be applied in _apply_theme
        
        # Preview controls
        preview_controls = QHBoxLayout()
        self.preview_btn = PButton("Preview", role="secondary", on_click=self.update_preview)
        self.preview_btn.setMaximumWidth(70)
        
        self.preview_rows_combo = QComboBox()
        self.preview_rows_combo.addItems(["5", "10", "20"])
        self.preview_rows_combo.setCurrentText("5")
        self.preview_rows_combo.setMaximumWidth(50)
        
        preview_controls.addWidget(self.preview_btn)
        preview_controls.addWidget(QLabel("rows:"))
        preview_controls.addWidget(self.preview_rows_combo)
        preview_controls.addStretch()
        
        preview_layout.addLayout(preview_controls)
        preview_layout.addWidget(self.preview_text)
        
        layout.addWidget(preview_group)
    
    def create_action_buttons(self, layout):
        """Create action buttons section."""
        button_layout = QHBoxLayout()
        
        self.apply_btn = PButton("Apply", role="primary", on_click=self.apply_transform)
        # Remove hardcoded styling - will be applied in _apply_theme

        self.clear_btn = PButton("Clear", role="secondary", on_click=self.clear_panel)
        # Remove hardcoded styling - will be applied in _apply_theme
        
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
    
    def setup_connections(self):
        """Set up signal connections."""
        self.transform_type_combo.currentTextChanged.connect(self.on_transform_type_changed)
        self.source_column_list.itemSelectionChanged.connect(self.on_source_column_changed)
        # Connect transform controller signals
        self.transform_controller.transform_completed.connect(self.on_controller_transform_completed)
        self.transform_controller.transform_failed.connect(self.on_controller_transform_failed)
        self.transform_controller.preview_ready.connect(self.on_controller_preview_ready)
    
    def on_controller_transform_completed(self, dataset_id: str, column_name: str, result_data):
        """Handle successful transformation from controller."""
        self.logger.info(
            "TransformPanel controller transform completed for dataset %s, column %s", dataset_id, column_name
        )
        # The transform_applied signal is already emitted from apply_transform
    
    def on_controller_transform_failed(self, dataset_id: str, error_message: str):
        """Handle failed transformation from controller."""
        self.logger.error(
            "TransformPanel controller error for dataset %s: %s", dataset_id, error_message
        )
        self._last_transform_error = error_message
        self.preview_text.setPlainText(f"Transform failed: {error_message}")
    
    def on_controller_preview_ready(self, dataset_id: str, preview_data):
        """Handle preview data from controller."""
        self.logger.debug("TransformPanel preview ready for dataset %s", dataset_id)
    
    def set_active_dataset(self, dataset):
        """Update panel context when dataset tab becomes active."""
        if dataset is not None:
            self.current_dataset = dataset
            self.update_dataset_info()
            self.update_column_list()
            self.enable_controls(enabled=True)
        else:
            self.current_dataset = None
            self.clear_dataset_info()
            self.enable_controls(enabled=False)
    
    def update_dataset_info(self):
        """Update the dataset information display."""
        if self.current_dataset:
            dataset_name = getattr(self.current_dataset, "name", "Unknown Dataset")
            self.dataset_label.setText(dataset_name)
            
            # Get row count if available
            if hasattr(self.current_dataset, "data") and self.current_dataset.data is not None:
                try:
                    df = self.current_dataset.data
                    row_count = len(df)
                    col_count = len(df.columns)
                    self.row_count_label.setText(f"{row_count} rows, {col_count} columns")
                except Exception:
                    self.row_count_label.setText("Data info unavailable")
            else:
                self.row_count_label.setText("")
    
    def clear_dataset_info(self):
        """Clear dataset information display."""
        self.dataset_label.setText("No dataset selected")
        self.row_count_label.setText("")
    
    def get_selected_columns(self):
        """Get list of currently selected column names."""
        selected_items = self.source_column_list.selectedItems()
        return [item.text() for item in selected_items]
    
    def update_column_list(self):
        """Update the available columns list."""
        self.source_column_list.clear()
        self.available_columns = []
        
        if self.current_dataset and hasattr(self.current_dataset, "data") and self.current_dataset.data is not None:
            try:
                df = self.current_dataset.data
                self.available_columns = list(df.columns)
                self.source_column_list.addItems(self.available_columns)
            except Exception as e:
                self.logger.error("TransformPanel: error getting columns: %s", e, exc_info=True)
    
    def enable_controls(self, *, enabled: bool):
        """Enable or disable all controls based on dataset availability."""
        self.transform_type_combo.setEnabled(enabled)
        self.source_column_list.setEnabled(enabled)
        self.new_column_name.setEnabled(enabled)
        self.replace_column_check.setEnabled(enabled)
        self.function_text.setEnabled(enabled)
        self.preview_btn.setEnabled(enabled)
        self.apply_btn.setEnabled(enabled)

        # Enable function toolbar
        self.insert_function_btn.setEnabled(enabled)
        self.reference_btn.setEnabled(enabled)
    
    def on_transform_type_changed(self, transform_type: str):
        """Handle transform type selection change."""
        # Update function placeholder based on type
        placeholders = {
            "Custom Function": "Enter transformation function:\ne.g., x * 2, x.upper(), pd.to_datetime(x)",
            "Math Operations": "Enter math expression:\ne.g., x * 2, x + 10, np.sqrt(x)",
            "String Operations": "Enter string operation:\ne.g., x.upper(), x.strip(), x.replace('old', 'new')",
            "Date/Time Operations": "Enter date operation:\ne.g., pd.to_datetime(x), x.strftime('%Y-%m-%d')",
            "Statistical Operations": "Enter statistical function:\ne.g., (x - x.mean()) / x.std(), x.rank()"
        }
        
        placeholder = placeholders.get(transform_type, "Enter transformation function")
        self.function_text.setPlaceholderText(placeholder)
    
    def on_source_column_changed(self):
        """Handle source column selection change."""
        selected_columns = self.get_selected_columns()
        if selected_columns and not self.new_column_name.text():
            # Auto-suggest new column name
            if len(selected_columns) == 1:
                self.new_column_name.setText(f"{selected_columns[0]}_transformed")
            else:
                self.new_column_name.setText("combined_transformed")
    
    def insert_function_code(self, function_text: str):
        """Insert a ready-made function at the cursor, replacing any selection."""
        # If the box is empty, just set it; otherwise insert at the cursor so the
        # user can compose expressions from several inserted pieces.
        if not self.function_text.toPlainText().strip():
            self.function_text.setPlainText(function_text)
        else:
            self.function_text.insertPlainText(function_text)
        self.function_text.setFocus()

    def toggle_function_reference(self):
        """Show or hide the variables/functions reference."""
        self.function_reference.setVisible(not self.function_reference.isVisible())
    
    def update_preview(self):
        """Update the preview with sample transformation results."""
        selected_columns = self.get_selected_columns()
        if not self.current_dataset or not selected_columns:
            self.preview_text.setPlainText("No data available for preview")
            return
        
        source_column = selected_columns[0]  # Use first selected column for preview
        function_code = self.function_text.toPlainText().strip()
        
        if not function_code:
            self.preview_text.setPlainText("Enter a function to preview")
            return
        
        try:
            # Get dataset ID and preview rows
            dataset_id = getattr(self.current_dataset, "id", None)
            preview_rows = int(self.preview_rows_combo.currentText())
            
            if dataset_id:
                # Use controller to create preview
                preview_result = self.transform_controller.create_preview(
                    dataset_id=dataset_id,
                    source_column=source_column,
                    function_code=function_code,
                    preview_rows=preview_rows
                )
                
                if preview_result and "error" not in preview_result:
                    # Format preview display
                    preview_text = f"Source ({source_column}):\n"
                    for i, value in enumerate(preview_result["source_values"]):
                        preview_text += f"  {i+1}: {value}\n"
                    
                    preview_text += f"\nFunction: {function_code}\n"
                    preview_text += "Transformed:\n"
                    for i, value in enumerate(preview_result["transformed_values"]):
                        preview_text += f"  {i+1}: {value}\n"
                    
                    self.preview_text.setPlainText(preview_text)
                else:
                    error_msg = preview_result.get("error", "Preview generation failed") if preview_result else "Preview unavailable"
                    self.preview_text.setPlainText(f"Preview error: {error_msg}")
            else:
                # Fallback to simple preview without controller
                df = self.current_dataset.get_dataframe()
                preview_data = df[source_column].head(preview_rows)
                
                preview_text = f"Source ({source_column}):\n"
                for i, value in enumerate(preview_data):
                    preview_text += f"  {i+1}: {value}\n"
                
                preview_text += f"\nFunction: {function_code}\n"
                preview_text += "Transformed:\n"
                preview_text += "  (Preview will be calculated on apply)\n"
                
                self.preview_text.setPlainText(preview_text)
            
            # Preview updated - could publish preview event if needed
            pass
            
        except Exception as e:
            self.preview_text.setPlainText(f"Preview error: {str(e)}")
    
    def apply_transform(self):
        """Apply the transformation to the dataset."""
        selected_columns = self.get_selected_columns()
        if not self.current_dataset or not selected_columns:
            self.logger.warning("TransformPanel: no dataset or source column selected for transform")
            return
        
        source_column = selected_columns[0]  # Use first selected column for transformation
        new_column_name = self.new_column_name.text().strip()
        function_code = self.function_text.toPlainText().strip()
        replace_existing = self.replace_column_check.isChecked()
        
        if not new_column_name:
            self.logger.warning("TransformPanel: no new column name provided")
            return
        
        if not function_code:
            self.logger.warning("TransformPanel: no transformation function provided")
            return
        
        try:
            # Get dataset ID
            dataset_id = getattr(self.current_dataset, "id", None)
            if not dataset_id:
                self.logger.warning("TransformPanel: dataset id not available; aborting transform")
                return

            # Apply transformation through controller
            self._last_transform_error = None
            success = self.transform_controller.apply_transformation(
                dataset_id=dataset_id,
                source_column=source_column,
                new_column_name=new_column_name,
                function_code=function_code,
                replace_existing=replace_existing
            )

            if success:
                # The command emits the structured column-added / data-changed
                # events that refresh the data tab and column-source selectors.
                self.logger.info("TransformPanel: transform applied %s -> %s using %s", source_column, new_column_name, function_code)
                # Clear the panel after successful transform
                self.clear_panel()
            else:
                self.logger.error("TransformPanel: transform failed - see logs for details")
                # transform_controller.transform_failed is emitted synchronously and
                # already wrote the specific message to preview_text; fall back to a
                # generic one only if that signal wasn't the source of the failure.
                if not self._last_transform_error:
                    self.preview_text.setPlainText("Transform failed - see logs for details")

        except Exception as e:
            self.logger.error("TransformPanel: transform failed: %s", e, exc_info=True)
            self.preview_text.setPlainText(f"Transform failed: {e}")
    
    def clear_panel(self):
        """Reset panel to initial state."""
        self.function_text.clear()
        self.new_column_name.clear()
        self.preview_text.clear()
        self.replace_column_check.setChecked(False)
        
        # Reset to first column if available
        if self.source_column_list.count() > 0:
            self.source_column_list.setCurrentRow(0)
        
        # Reset to default transform type
        self.transform_type_combo.setCurrentText("Custom Function")
    
    def get_available_columns(self) -> list:
        """Get column names from current active dataset."""
        return self.available_columns.copy()
    
    def setup_event_subscriptions(self):
        """Setup event subscriptions for this component."""
        self.subscribe_to_multiple_events([
            # Specific dataset operations (for detailed column handling)
            (DatasetOperationEvents.DATASET_COLUMN_ADDED, self.on_column_added),
            (DatasetOperationEvents.DATASET_COLUMN_REMOVED, self.on_column_removed),
            
            # UI events
            (UIEvents.TAB_CHANGED, self.on_tab_changed),
        ])
    
    def on_column_added(self, event_data):
        """Handle specific column additions."""
        dataset_id = event_data.get("dataset_id")
        if self.current_dataset and hasattr(self.current_dataset, "id") and dataset_id == self.current_dataset.id:
            self.refresh_column_list()
    
    def on_column_removed(self, event_data):
        """Handle specific column removals.""" 
        dataset_id = event_data.get("dataset_id")
        if self.current_dataset and hasattr(self.current_dataset, "id") and dataset_id == self.current_dataset.id:
            self.refresh_column_list()
    
    def on_tab_changed(self, event_data):
        """Handle tab change events."""
        if event_data.get("tab_type") == "dataset":
            # Update context for new dataset tab
            dataset_id = event_data.get("dataset_id")
            project = self.app_context.app_state.current_project
            if project:
                dataset = project.find_item(dataset_id)
                self.set_active_dataset(dataset)
            else:
                self.set_active_dataset(None)
        
            self.refresh_ui_state()
    
    def refresh_ui_state(self):
        """Refresh the UI state when dataset changes."""
        self.logger.debug("Refreshing UI state")
        self.refresh_column_list()
        self.clear_panel()
    
    def refresh_column_list(self):
        """Refresh the column list from current dataset."""
        if self.current_dataset and hasattr(self.current_dataset, "data") and self.current_dataset.data is not None:
            self.available_columns = list(self.current_dataset.data.columns)
            self.source_column_list.clear()
            self.source_column_list.addItems(self.available_columns)
