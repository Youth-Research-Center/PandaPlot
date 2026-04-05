"""
Base dialog for analysis operations.
"""

from typing import Any, Dict, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from pandaplot.models.project.items.dataset import Dataset


class BaseAnalysisDialog(QDialog):
    """
    Base dialog for analysis operations with common UI components.
    """
    
    def __init__(self, parent, dataset: Dataset, default_y_column: Optional[str] = None):
        super().__init__(parent)
        self.dataset = dataset
        self.default_y_column = default_y_column
        
        self.setWindowTitle("Analysis Configuration")
        self.setModal(True)
        self.resize(400, 500)
        
        self.setup_ui()
        self.setup_column_choices()
        
        if default_y_column:
            self.y_column_combo.setCurrentText(default_y_column)
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Column selection
        column_group = self.create_column_selection_group()
        layout.addWidget(column_group)
        
        # Parameters
        params_group = self.create_parameters_group()
        layout.addWidget(params_group)
        
        # Range selection
        range_group = self.create_range_selection_group()
        layout.addWidget(range_group)
        
        # Preview/Results
        preview_group = self.create_preview_group()
        layout.addWidget(preview_group)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def create_column_selection_group(self) -> QGroupBox:
        """Create column selection group."""
        group = QGroupBox("Column Selection")
        layout = QFormLayout()
        
        self.x_column_combo = QComboBox()
        self.y_column_combo = QComboBox()
        
        layout.addRow("X Column:", self.x_column_combo)
        layout.addRow("Y Column:", self.y_column_combo)
        
        # Result column naming
        self.result_column_name = QLineEdit()
        self.replace_existing = QCheckBox("Replace if exists")
        
        layout.addRow("Result Column:", self.result_column_name)
        layout.addRow("", self.replace_existing)
        
        group.setLayout(layout)
        return group
    
    def create_parameters_group(self) -> QGroupBox:
        """Create parameters group - to be overridden by subclasses."""
        group = QGroupBox("Parameters")
        layout = QFormLayout()
        group.setLayout(layout)
        return group
    
    def create_range_selection_group(self) -> QGroupBox:
        """Create data range selection group."""
        group = QGroupBox("Data Range")
        layout = QFormLayout()
        
        self.start_index = QSpinBox()
        self.start_index.setMinimum(0)
        self.start_index.setValue(0)
        
        self.end_index = QSpinBox()
        self.end_index.setMinimum(-1)
        self.end_index.setValue(-1)
        self.end_index.setSpecialValueText("End")
        
        layout.addRow("Start Index:", self.start_index)
        layout.addRow("End Index:", self.end_index)
        
        group.setLayout(layout)
        return group
    
    def create_preview_group(self) -> QGroupBox:
        """Create preview group."""
        group = QGroupBox("Preview")
        layout = QVBoxLayout()
        
        preview_btn = QPushButton("Preview Analysis")
        preview_btn.clicked.connect(self.preview_analysis)
        
        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setReadOnly(True)
        
        layout.addWidget(preview_btn)
        layout.addWidget(self.preview_text)
        
        group.setLayout(layout)
        return group
    
    def setup_column_choices(self):
        """Setup column choices from dataset."""
        if self.dataset and hasattr(self.dataset, "data") and self.dataset.data is not None:
            columns = list(self.dataset.data.columns)
            
            self.x_column_combo.addItems(columns)
            self.y_column_combo.addItems(columns)
            
            # Set defaults
            if len(columns) >= 2:
                self.x_column_combo.setCurrentIndex(0)
                self.y_column_combo.setCurrentIndex(1)
            elif len(columns) == 1:
                self.x_column_combo.setCurrentIndex(0)
                self.y_column_combo.setCurrentIndex(0)
            
            # Update max values for range selection
            max_rows = len(self.dataset.data)
            self.start_index.setMaximum(max_rows - 1)
            self.end_index.setMaximum(max_rows)
    
    def preview_analysis(self):
        """Preview the analysis - to be implemented by subclasses."""
        self.preview_text.setText("Preview not implemented for this analysis type.")
    
    def get_analysis_config(self) -> Dict[str, Any]:
        """Get analysis configuration - to be implemented by subclasses."""
        base_config = {
            "x_column": self.x_column_combo.currentText(),
            "y_column": self.y_column_combo.currentText(),
            "new_column_name": self.result_column_name.text().strip(),
            "replace_existing": self.replace_existing.isChecked(),
            "parameters": {
                "start_index": self.start_index.value(),
                "end_index": self.end_index.value() if self.end_index.value() != -1 else -1
            }
        }
        return base_config
