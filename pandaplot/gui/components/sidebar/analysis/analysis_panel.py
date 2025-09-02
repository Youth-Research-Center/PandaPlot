"""
Analysis panel for mathematical operations on dataset columns.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QComboBox, QSpinBox, QLineEdit, QPushButton, QCheckBox,
    QTextEdit, QScrollArea
)
from PySide6.QtCore import Qt
from typing import Dict, Any, Optional, override

from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.state.app_context import AppContext
from pandaplot.analysis import AnalysisEngine
from pandaplot.commands.project.dataset.analysis_command import AnalysisCommand
from pandaplot.models.events import (
    AnalysisEvents, UIEvents, DatasetEvents, DatasetOperationEvents
)
from pandaplot.models.project.items import Dataset


class AnalysisPanel(PWidget):
    """
    Side panel for mathematical analysis operations on dataset columns.
    """

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.current_dataset = None
        self.current_dataset_id = None

        self._init_ui()
        self.setup_connections()
        self.setup_event_subscriptions()

    @override
    def _init_ui(self):
        """Setup the user interface."""
        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        
        # Panel title
        title_label = QLabel("📊 Analysis Operations")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                padding: 5px;
                background-color: #ecf0f1;
                border-radius: 3px;
            }
        """)
        main_layout.addWidget(title_label)
        
        # Scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(10)
        
        # Analysis type selection
        self.create_analysis_type_section(content_layout)
        
        # Column selection
        self.create_column_selection_section(content_layout)
        
        # Parameters section
        self.create_parameters_section(content_layout)
        
        # Data range section
        self.create_range_section(content_layout)
        
        # Result configuration
        self.create_result_section(content_layout)
        
        # Preview section
        self.create_preview_section(content_layout)
        
        # Action buttons
        self.create_action_buttons(content_layout)
        
        # Add stretch to push everything to top
        content_layout.addStretch()
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
    
    @override
    def _apply_theme(self):
        pass

    def create_analysis_type_section(self, layout):
        """Create analysis type selection section."""
        group = QGroupBox("Analysis Type")
        group_layout = QFormLayout()
        
        self.analysis_type_combo = QComboBox()
        self.analysis_type_combo.addItems([
            "Derivative",
            "Integral", 
            "Arc Length",
            "Smoothing",
            "Interpolation"
        ])
        self.analysis_type_combo.currentTextChanged.connect(self.on_analysis_type_changed)
        
        group_layout.addRow("Type:", self.analysis_type_combo)
        group.setLayout(group_layout)
        layout.addWidget(group)
    
    def create_column_selection_section(self, layout):
        """Create column selection section."""
        group = QGroupBox("Column Selection")
        group_layout = QFormLayout()
        
        self.x_column_combo = QComboBox()
        self.y_column_combo = QComboBox()
        
        group_layout.addRow("X Column:", self.x_column_combo)
        group_layout.addRow("Y Column:", self.y_column_combo)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
    
    def create_parameters_section(self, layout):
        """Create dynamic parameters section."""
        self.parameters_group = QGroupBox("Parameters")
        self.parameters_layout = QFormLayout()
        self.parameters_group.setLayout(self.parameters_layout)
        layout.addWidget(self.parameters_group)
        
        # This will be populated dynamically based on analysis type
        self.update_parameters_ui()
    
    def create_range_section(self, layout):
        """Create data range selection section."""
        group = QGroupBox("Data Range")
        group_layout = QFormLayout()
        
        self.start_index = QSpinBox()
        self.start_index.setMinimum(0)
        self.start_index.setValue(0)
        
        self.end_index = QSpinBox()
        self.end_index.setMinimum(-1)
        self.end_index.setValue(-1)
        self.end_index.setSpecialValueText("End")
        
        group_layout.addRow("Start Index:", self.start_index)
        group_layout.addRow("End Index:", self.end_index)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
    
    def create_result_section(self, layout):
        """Create result configuration section."""
        group = QGroupBox("Result Configuration")
        group_layout = QFormLayout()
        
        self.result_column_name = QLineEdit()
        self.result_column_name.setPlaceholderText("Enter column name...")
        
        self.replace_existing = QCheckBox("Replace if exists")
        
        group_layout.addRow("Result Column:", self.result_column_name)
        group_layout.addRow("", self.replace_existing)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
    
    def create_preview_section(self, layout):
        """Create preview section."""
        group = QGroupBox("Preview")
        group_layout = QVBoxLayout()
        
        self.preview_btn = QPushButton("🔍 Preview Analysis")
        self.preview_btn.clicked.connect(self.preview_analysis)
        self.preview_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(120)
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Preview results will appear here...")
        
        group_layout.addWidget(self.preview_btn)
        group_layout.addWidget(self.preview_text)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
    
    def create_action_buttons(self, layout):
        """Create action buttons section."""
        button_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("✅ Apply Analysis")
        self.apply_btn.clicked.connect(self.apply_analysis)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        
        self.clear_btn = QPushButton("🔄 Clear")
        self.clear_btn.clicked.connect(self.clear_inputs)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
    
    def setup_connections(self):
        """Setup signal connections."""
        # Connect column selection changes to auto-generate result names
        self.y_column_combo.currentTextChanged.connect(self.auto_generate_result_name)
        self.analysis_type_combo.currentTextChanged.connect(self.auto_generate_result_name)
    
    def update_context(self, tab_widget):
        """Update the panel context based on the current tab."""
        if not tab_widget:
            self.current_dataset = None
            self.current_dataset_id = None
            self.setEnabled(False)
            return
        
        # Check if this is a dataset tab
        if hasattr(tab_widget, 'dataset') and tab_widget.dataset:
            self.current_dataset = tab_widget.dataset
            self.current_dataset_id = tab_widget.dataset.id
            self.setEnabled(True)
            self.update_column_choices()
        else:
            self.current_dataset = None
            self.current_dataset_id = None
            self.setEnabled(False)
    
    def update_column_choices(self):
        """Update column choices based on current dataset."""
        if not self.current_dataset or not hasattr(self.current_dataset, 'data'):
            return
        
        df = self.current_dataset.data
        if df is None:
            return
        
        # Clear existing items
        self.x_column_combo.clear()
        self.y_column_combo.clear()
        
        # Add column names
        columns = list(df.columns)
        self.x_column_combo.addItems(columns)
        self.y_column_combo.addItems(columns)
        
        # Set defaults if possible
        if len(columns) >= 2:
            self.x_column_combo.setCurrentIndex(0)
            self.y_column_combo.setCurrentIndex(1)
        elif len(columns) == 1:
            self.x_column_combo.setCurrentIndex(0)
            self.y_column_combo.setCurrentIndex(0)
        
        # Update range limits
        max_rows = len(df)
        self.start_index.setMaximum(max_rows - 1)
        self.end_index.setMaximum(max_rows)
    
    def on_analysis_type_changed(self):
        """Handle analysis type change."""
        self.update_parameters_ui()
        self.auto_generate_result_name()
    
    def update_parameters_ui(self):
        """Update parameters UI based on selected analysis type."""
        # Clear existing parameters
        while self.parameters_layout.count():
            child = self.parameters_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        analysis_type = self.analysis_type_combo.currentText()
        
        if analysis_type == "Derivative":
            self.method_combo = QComboBox()
            self.method_combo.addItems(["Central Difference", "Forward Difference", "Backward Difference"])
            self.parameters_layout.addRow("Method:", self.method_combo)
            
        elif analysis_type == "Integral":
            info_label = QLabel("Method: Trapezoidal Rule")
            info_label.setStyleSheet("color: #666666; font-style: italic;")
            self.parameters_layout.addRow("", info_label)
            
        elif analysis_type == "Arc Length":
            info_label = QLabel("Method: Euclidean Distance")
            info_label.setStyleSheet("color: #666666; font-style: italic;")
            self.parameters_layout.addRow("", info_label)
            
        elif analysis_type == "Smoothing":
            self.smooth_method_combo = QComboBox()
            self.smooth_method_combo.addItems(["Savitzky-Golay", "Rolling Mean", "LOWESS"])
            self.smooth_method_combo.currentTextChanged.connect(self.update_smoothing_params)
            self.parameters_layout.addRow("Method:", self.smooth_method_combo)
            
            # Additional parameters will be added by update_smoothing_params
            self.update_smoothing_params()
            
        elif analysis_type == "Interpolation":
            self.interp_method_combo = QComboBox()
            self.interp_method_combo.addItems(["Linear", "Cubic", "Quadratic", "Nearest"])
            self.parameters_layout.addRow("Method:", self.interp_method_combo)
            
            self.num_points_spin = QSpinBox()
            self.num_points_spin.setRange(10, 10000)
            self.num_points_spin.setValue(100)
            self.parameters_layout.addRow("Points:", self.num_points_spin)
    
    def update_smoothing_params(self):
        """Update smoothing parameters based on method."""
        if not hasattr(self, 'smooth_method_combo'):
            return
        
        method = self.smooth_method_combo.currentText()
        
        # Remove existing additional parameters
        while self.parameters_layout.rowCount() > 1:
            self.parameters_layout.removeRow(1)
        
        if method == "Savitzky-Golay":
            self.window_length_spin = QSpinBox()
            self.window_length_spin.setRange(3, 101)
            self.window_length_spin.setValue(11)
            self.parameters_layout.addRow("Window Length:", self.window_length_spin)
            
            self.poly_order_spin = QSpinBox()
            self.poly_order_spin.setRange(1, 10)
            self.poly_order_spin.setValue(3)
            self.parameters_layout.addRow("Polynomial Order:", self.poly_order_spin)
            
        elif method == "Rolling Mean":
            self.window_spin = QSpinBox()
            self.window_spin.setRange(2, 50)
            self.window_spin.setValue(5)
            self.parameters_layout.addRow("Window Size:", self.window_spin)
            
        # LOWESS doesn't need additional parameters in the UI
    
    def auto_generate_result_name(self):
        """Auto-generate result column name."""
        y_column = self.y_column_combo.currentText()
        analysis_type = self.analysis_type_combo.currentText().lower()
        
        if y_column and analysis_type:
            result_name = f"{y_column}_{analysis_type.replace(' ', '_')}"
            self.result_column_name.setText(result_name)
    
    def preview_analysis(self):
        """Preview the analysis operation."""
        try:
            if not self.validate_inputs():
                return
            
            config = self.get_analysis_config()
            
            if self.current_dataset is None:
                return
            
            # Get data
            df = self.current_dataset.data
            if df is None:
                return
            x_data = df[config['x_column']]
            y_data = df[config['y_column']]
            
            # Execute analysis preview
            result = self.execute_analysis_preview(x_data, y_data, config)
            
            if result is not None:
                # Display preview
                preview_text = f"Analysis Preview: {config['analysis_type'].title()}\n"
                preview_text += f"Columns: {config['x_column']} → {config['y_column']}\n"
                preview_text += f"Data Range: {config['parameters']['start_index']} to "
                preview_text += f"{config['parameters']['end_index'] if config['parameters']['end_index'] != -1 else 'end'}\n"
                preview_text += f"Result Points: {len(result.result_data)}\n\n"
                preview_text += "Statistics:\n"
                for key, value in result.statistics.items():
                    preview_text += f"  {key.replace('_', ' ').title()}: {value:.6f}\n"
                
                self.preview_text.setText(preview_text)
            else:
                self.preview_text.setText("Preview failed. Please check your parameters.")
                
        except Exception as e:
            self.preview_text.setText(f"Preview error: {str(e)}")
    
    def execute_analysis_preview(self, x_data, y_data, config):
        """Execute analysis for preview purposes."""
        analysis_type = config['analysis_type']
        params = config['parameters']
        
        if analysis_type == 'derivative':
            return AnalysisEngine.calculate_derivative(
                x_data, y_data, params.get('method', 'central'),
                params['start_index'], params['end_index']
            )
        elif analysis_type == 'integral':
            return AnalysisEngine.calculate_integral(
                x_data, y_data, params['start_index'], params['end_index']
            )
        elif analysis_type == 'arc_length':
            return AnalysisEngine.calculate_arc_length(
                x_data, y_data, params['start_index'], params['end_index']
            )
        elif analysis_type == 'smoothing':
            additional_params = {k: v for k, v in params.items() 
                               if k not in ['start_index', 'end_index', 'method']}
            return AnalysisEngine.smooth_data(
                x_data, y_data, params.get('method', 'savgol'),
                params['start_index'], params['end_index'], **additional_params
            )
        elif analysis_type == 'interpolation':
            return AnalysisEngine.interpolate_data(
                x_data, y_data, params.get('method', 'cubic'),
                params.get('num_points'), params['start_index'], params['end_index']
            )
        
        return None
    
    def apply_analysis(self):
        """Apply the analysis operation."""
        try:
            if not self.validate_inputs():
                return
            
            config = self.get_analysis_config()
            
            # Create and execute command
            if self.current_dataset_id:
                command = AnalysisCommand(self.app_context, self.current_dataset_id, config)
                
                execution_result = self.app_context.get_command_executor().execute_command(command)
                
                if execution_result:
                    # Publish analysis completion event
                    self.publish_event(AnalysisEvents.ANALYSIS_COMPLETED, {
                        'dataset_id': self.current_dataset_id,
                        'new_column_name': config['new_column_name'],
                        'analysis_type': config['analysis_type'],
                        'analysis_config': config
                    })
                    
                    # Also publish dataset column added event for UI updates
                    self.publish_event(DatasetOperationEvents.DATASET_COLUMN_ADDED, {
                        'dataset_id': self.current_dataset_id,
                        'column_name': config['new_column_name'],
                        'operation': 'analysis',
                        'source': 'analysis_panel'
                    })
                    
                    self.preview_text.setText(f"✅ Analysis applied successfully!\nColumn '{config['new_column_name']}' added to dataset.")
                else:
                    self.logger.error("Command execution failed for dataset %s", self.current_dataset_id)
                    self.preview_text.setText("❌ Command execution failed. Please check your inputs.")
            else:
                self.preview_text.setText("❌ Failed to apply analysis. Please check your inputs.")
                
        except Exception as e:
            self.preview_text.setText(f"❌ Error applying analysis: {str(e)}")
    
    def validate_inputs(self) -> bool:
        """Validate all inputs."""
        if self.current_dataset is None:
            self.preview_text.setText("❌ No dataset selected.")
            return False

        if not hasattr(self.current_dataset, 'data') or self.current_dataset.data is None:
            self.preview_text.setText("❌ Dataset data is not available.")
            return False
        
        if not self.x_column_combo.currentText() or not self.y_column_combo.currentText():
            self.preview_text.setText("❌ Please select both X and Y columns.")
            return False
        
        if not self.result_column_name.text().strip():
            self.preview_text.setText("❌ Please enter a result column name.")
            return False
        
        return True
    
    def get_analysis_config(self) -> Dict[str, Any]:
        """Get current analysis configuration."""
        analysis_type_map = {
            "Derivative": "derivative",
            "Integral": "integral",
            "Arc Length": "arc_length",
            "Smoothing": "smoothing",
            "Interpolation": "interpolation"
        }
        
        config = {
            'analysis_type': analysis_type_map[self.analysis_type_combo.currentText()],
            'x_column': self.x_column_combo.currentText(),
            'y_column': self.y_column_combo.currentText(),
            'new_column_name': self.result_column_name.text().strip(),
            'replace_existing': self.replace_existing.isChecked(),
            'parameters': {
                'start_index': self.start_index.value(),
                'end_index': self.end_index.value() if self.end_index.value() != -1 else -1
            }
        }
        
        # Add analysis-specific parameters
        analysis_type = self.analysis_type_combo.currentText()
        
        if analysis_type == "Derivative" and hasattr(self, 'method_combo'):
            method_map = {
                "Central Difference": "central",
                "Forward Difference": "forward",
                "Backward Difference": "backward"
            }
            config['parameters']['method'] = method_map[self.method_combo.currentText()]
            
        elif analysis_type == "Smoothing" and hasattr(self, 'smooth_method_combo'):
            method_map = {
                "Savitzky-Golay": "savgol",
                "Rolling Mean": "rolling_mean",
                "LOWESS": "lowess"
            }
            config['parameters']['method'] = method_map[self.smooth_method_combo.currentText()]
            
            if hasattr(self, 'window_length_spin'):
                config['parameters']['window_length'] = self.window_length_spin.value()
            if hasattr(self, 'poly_order_spin'):
                config['parameters']['polynomial_order'] = self.poly_order_spin.value()
            if hasattr(self, 'window_spin'):
                config['parameters']['window'] = self.window_spin.value()
                
        elif analysis_type == "Interpolation" and hasattr(self, 'interp_method_combo'):
            method_map = {
                "Linear": "linear",
                "Cubic": "cubic", 
                "Quadratic": "quadratic",
                "Nearest": "nearest"
            }
            config['parameters']['method'] = method_map[self.interp_method_combo.currentText()]
            if hasattr(self, 'num_points_spin'):
                config['parameters']['num_points'] = self.num_points_spin.value()
        
        return config
    
    def clear_inputs(self):
        """Clear all input fields."""
        self.result_column_name.clear()
        self.replace_existing.setChecked(False)
        self.start_index.setValue(0)
        self.end_index.setValue(-1)
        self.preview_text.clear()
        
        # Reset to defaults
        self.analysis_type_combo.setCurrentIndex(0)
    
    @override
    def setup_event_subscriptions(self):
        """Setup event subscriptions for this component."""
        super().setup_event_subscriptions()

        self.subscribe_to_multiple_events([
            # Generic dataset change (for broad awareness)
            (DatasetEvents.DATASET_CHANGED, self.on_dataset_changed),
            
            # Specific dataset operations (for detailed column handling)
            (DatasetOperationEvents.DATASET_COLUMN_ADDED, self.on_column_added),
            (DatasetOperationEvents.DATASET_COLUMN_REMOVED, self.on_column_removed),
            
            # UI events
            (UIEvents.TAB_CHANGED, self.on_tab_changed),
        ])
    
    def on_dataset_changed(self, event_data):
        """Handle generic dataset changes."""
        dataset_id = event_data.get('dataset_id')
        if dataset_id == self.current_dataset_id:
            self.refresh_ui_state()
    
    def on_column_added(self, event_data):
        """Handle specific column additions."""
        dataset_id = event_data.get('dataset_id')
        column_name = event_data.get('column_name')
        if dataset_id == self.current_dataset_id and column_name:
            # Refresh column choices
            self.refresh_column_choices()
    
    def on_column_removed(self, event_data):
        """Handle specific column removals."""
        dataset_id = event_data.get('dataset_id')
        column_name = event_data.get('column_name')
        if dataset_id == self.current_dataset_id and column_name:
            # Refresh column choices
            self.refresh_column_choices()
    
    def on_tab_changed(self, event_data):
        """Handle tab change events."""
        if event_data.get('tab_type') == 'dataset':
            new_dataset_id = event_data.get('dataset_id')
            if new_dataset_id != self.current_dataset_id:
                self.current_dataset_id = new_dataset_id
                
                # Get the actual dataset object from the project
                if new_dataset_id:
                    project = self.app_context.get_app_state().current_project
                    if project:
                        dataset = project.find_item(new_dataset_id)
                        if isinstance(dataset, Dataset):
                            self.current_dataset = dataset
                        else:
                            self.current_dataset = None
                    else:
                        self.current_dataset = None
                else:
                    self.current_dataset = None
                
                # Refresh the column choices
                self.update_column_choices()
        else:
            # Clear dataset context for non-dataset tabs
            self.current_dataset = None
            self.current_dataset_id = None
            self.update_column_choices()
    
    def refresh_ui_state(self):
        """Refresh the UI state when dataset changes."""
        self.update_column_choices()
    
    def refresh_column_choices(self):
        """Refresh the column choices in the combo boxes."""
        self.update_column_choices()
        if self.x_column_combo.count() > 0:
            self.x_column_combo.setCurrentIndex(0)
        if self.y_column_combo.count() > 1:
            self.y_column_combo.setCurrentIndex(1)
