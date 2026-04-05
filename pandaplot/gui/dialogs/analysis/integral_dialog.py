"""
Dialog for integral analysis configuration.
"""

from typing import Any, Dict, Optional

from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel

from pandaplot.analysis import AnalysisEngine, AnalysisType

from .base_analysis_dialog import BaseAnalysisDialog


class IntegralDialog(BaseAnalysisDialog):
    """
    Dialog for configuring integral calculations.
    """
    
    def __init__(self, parent, dataset, default_y_column: Optional[str] = None):
        super().__init__(parent, dataset, default_y_column)
        self.setWindowTitle("Calculate Integral")
        
        # Set default result column name
        if default_y_column:
            self.result_column_name.setText(f"{default_y_column}_integral")
        else:
            self.result_column_name.setText("integral")
    
    def create_parameters_group(self) -> QGroupBox:
        """Create integral-specific parameters."""
        group = QGroupBox("Integral Parameters")
        layout = QFormLayout()
        
        # Method info (trapezoidal rule is used)
        method_label = QLabel("Method: Trapezoidal Rule")
        method_label.setStyleSheet("color: #666666; font-style: italic;")
        layout.addRow("", method_label)
        
        group.setLayout(layout)
        return group
    
    def preview_analysis(self):
        """Preview integral calculation."""
        try:
            if self.dataset is None or not hasattr(self.dataset, "data") or self.dataset.data is None:
                self.preview_text.setText("No dataset available for preview.")
                return
            
            x_col = self.x_column_combo.currentText()
            y_col = self.y_column_combo.currentText()
            
            if not x_col or not y_col:
                self.preview_text.setText("Please select both X and Y columns.")
                return
            
            # Calculate preview
            x_data = self.dataset.data[x_col]
            y_data = self.dataset.data[y_col]
            
            start_idx = self.start_index.value()
            end_idx = self.end_index.value() if self.end_index.value() != -1 else len(x_data)
            
            result = AnalysisEngine.calculate_integral(
                x_data, y_data, start_idx, end_idx
            )
            
            # Display preview
            preview_text = "Integral Analysis Preview\n"
            preview_text += "Method: Trapezoidal Rule\n"
            preview_text += f"Data Range: {start_idx} to {end_idx}\n"
            preview_text += f"Points: {len(result.result_data)}\n\n"
            preview_text += "Statistics:\n"
            for key, value in result.statistics.items():
                preview_text += f"  {key.replace('_', ' ').title()}: {value:.6f}\n"
            
            self.preview_text.setText(preview_text)
            
        except Exception as e:
            self.preview_text.setText(f"Preview error: {str(e)}")
    
    def get_analysis_config(self) -> Dict[str, Any]:
        """Get integral analysis configuration."""
        config = super().get_analysis_config()
        
        config.update({
            "analysis_type": AnalysisType.INTEGRAL.value,
            "parameters": {
                **config["parameters"],
                "method": "trapezoidal"
            }
        })
        
        return config
