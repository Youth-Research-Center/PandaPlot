"""
Dialog for derivative analysis configuration.
"""

from typing import Any, Dict, Optional

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox

from pandaplot.analysis import AnalysisEngine, AnalysisType

from .base_analysis_dialog import BaseAnalysisDialog


class DerivativeDialog(BaseAnalysisDialog):
    """
    Dialog for configuring derivative calculations.
    """
    
    def __init__(self, parent, dataset, default_y_column: Optional[str] = None):
        super().__init__(parent, dataset, default_y_column)
        self.setWindowTitle("Calculate Derivative")
        
        # Set default result column name
        if default_y_column:
            self.result_column_name.setText(f"{default_y_column}_derivative")
        else:
            self.result_column_name.setText("derivative")
    
    def create_parameters_group(self) -> QGroupBox:
        """Create derivative-specific parameters."""
        group = QGroupBox("Derivative Parameters")
        layout = QFormLayout()
        
        # Method selection
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Central Difference",
            "Forward Difference", 
            "Backward Difference"
        ])
        self.method_combo.setCurrentText("Central Difference")
        
        layout.addRow("Method:", self.method_combo)
        
        group.setLayout(layout)
        return group
    
    def preview_analysis(self):
        """Preview derivative calculation."""
        try:
            if self.dataset is None or not hasattr(self.dataset, "data") or self.dataset.data is None:
                self.preview_text.setText("No dataset available for preview.")
                return
            
            x_col = self.x_column_combo.currentText()
            y_col = self.y_column_combo.currentText()
            
            if not x_col or not y_col:
                self.preview_text.setText("Please select both X and Y columns.")
                return
            
            # Get method
            method_map = {
                "Central Difference": "central",
                "Forward Difference": "forward",
                "Backward Difference": "backward"
            }
            method = method_map[self.method_combo.currentText()]
            
            # Calculate preview on subset of data
            x_data = self.dataset.data[x_col]
            y_data = self.dataset.data[y_col]
            
            start_idx = self.start_index.value()
            end_idx = self.end_index.value() if self.end_index.value() != -1 else len(x_data)
            
            result = AnalysisEngine.calculate_derivative(
                x_data, y_data, method, start_idx, end_idx
            )
            
            # Display preview
            preview_text = "Derivative Analysis Preview\n"
            preview_text += f"Method: {method.title()}\n"
            preview_text += f"Data Range: {start_idx} to {end_idx}\n"
            preview_text += f"Points: {len(result.result_data)}\n\n"
            preview_text += "Statistics:\n"
            for key, value in result.statistics.items():
                preview_text += f"  {key.replace('_', ' ').title()}: {value:.6f}\n"
            
            self.preview_text.setText(preview_text)
            
        except Exception as e:
            self.preview_text.setText(f"Preview error: {str(e)}")
    
    def get_analysis_config(self) -> Dict[str, Any]:
        """Get derivative analysis configuration."""
        config = super().get_analysis_config()
        
        # Map display name to internal method name
        method_map = {
            "Central Difference": "central",
            "Forward Difference": "forward", 
            "Backward Difference": "backward"
        }
        
        config.update({
            "analysis_type": AnalysisType.DERIVATIVE.value,
            "parameters": {
                **config["parameters"],
                "method": method_map[self.method_combo.currentText()]
            }
        })
        
        return config
