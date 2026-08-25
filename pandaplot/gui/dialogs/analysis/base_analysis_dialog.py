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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from pandaplot.gui.components.common.p_button import PButton
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
        self._connect_range_signals()

        if default_y_column:
            self.y_column_combo.setCurrentText(default_y_column)

        self._update_range_labels()
    
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

        # Both spinboxes show 1-based row numbers, matching the row numbers
        # in the dataset table (pandas_table_model.py shows "row + 1").
        self.start_index = QSpinBox()
        self.start_index.setMinimum(0)
        self.start_index.setValue(0)
        self.start_value_label = QLabel("–")
        start_row = QHBoxLayout()
        start_row.addWidget(self.start_index)
        start_row.addWidget(self.start_value_label)
        layout.addRow("Start Row:", start_row)

        self.end_index = QSpinBox()
        self.end_index.setMinimum(0)
        self.end_index.setValue(0)
        self.end_value_label = QLabel("–")
        end_row = QHBoxLayout()
        end_row.addWidget(self.end_index)
        end_row.addWidget(self.end_value_label)
        layout.addRow("End Row:", end_row)

        group.setLayout(layout)
        return group

    def _connect_range_signals(self):
        self.start_index.valueChanged.connect(self._update_range_labels)
        self.end_index.valueChanged.connect(self._update_range_labels)
        self.x_column_combo.currentIndexChanged.connect(self._update_range_labels)
        self.y_column_combo.currentIndexChanged.connect(self._update_range_labels)

    def _resolve_point(self, row_number: int) -> Optional[tuple]:
        """Return the resolved (x, y) at a 1-based row number, or None."""
        if self.dataset is None or self.dataset.data is None:
            return None
        x_col = self.x_column_combo.currentText()
        y_col = self.y_column_combo.currentText()
        if not x_col or not y_col or x_col not in self.dataset.data.columns \
                or y_col not in self.dataset.data.columns:
            return None
        x_data = self.dataset.data[x_col]
        y_data = self.dataset.data[y_col]
        index = row_number - 1
        if not (0 <= index < len(x_data)):
            return None
        try:
            return float(x_data.iloc[index]), float(y_data.iloc[index])
        except (TypeError, ValueError):
            return None

    def _format_point(self, point: Optional[tuple]) -> str:
        if point is None:
            return "–"
        x, y = point
        return f"x={x:.4g}, y={y:.4g}"

    def _update_range_labels(self):
        self.start_value_label.setText(self._format_point(self._resolve_point(self.start_index.value())))
        self.end_value_label.setText(self._format_point(self._resolve_point(self.end_index.value())))
    
    def create_preview_group(self) -> QGroupBox:
        """Create preview group."""
        group = QGroupBox("Preview")
        layout = QVBoxLayout()
        
        preview_btn = PButton(
            "Preview Analysis", role="secondary", on_click=self.preview_analysis
        )
        
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
            
            # Both spinboxes show 1-based row numbers (row 1..row_count),
            # matching the dataset table. end_index defaults to the last row
            # so decreasing it shrinks the segment.
            row_count = len(self.dataset.data)
            lo = 1 if row_count > 0 else 0
            self.start_index.setMinimum(lo)
            self.start_index.setMaximum(row_count)
            self.end_index.setMinimum(lo)
            self.end_index.setMaximum(row_count)
            self.end_index.setValue(row_count)
    
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
                # The spinboxes show 1-based row numbers; the engine wants a
                # 0-based start and an exclusive end boundary, which is the
                # displayed end row number unchanged (row N inclusive == an
                # exclusive boundary of N in 0-based terms).
                "start_index": self.start_index.value() - 1,
                "end_index": self.end_index.value(),
            }
        }
        return base_config
