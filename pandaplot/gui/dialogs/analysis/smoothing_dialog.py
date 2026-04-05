"""
Dialog for data smoothing configuration.
"""

from typing import Any, Dict, Optional

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QSpinBox

from pandaplot.analysis import AnalysisEngine, AnalysisType

from .base_analysis_dialog import BaseAnalysisDialog


class SmoothingDialog(BaseAnalysisDialog):
    """
    Dialog for configuring data smoothing.
    """
    
    def __init__(self, parent, dataset, default_y_column: Optional[str] = None):
        super().__init__(parent, dataset, default_y_column)
        self.setWindowTitle("Smooth Data")
        
        # Set default result column name
        if default_y_column:
            self.result_column_name.setText(f"{default_y_column}_smoothed")
        else:
            self.result_column_name.setText("smoothed")
    
    def create_parameters_group(self) -> QGroupBox:
        """Create smoothing-specific parameters."""
        group = QGroupBox("Smoothing Parameters")
        layout = QFormLayout()
        
        # Method selection
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Savitzky-Golay",
            "Rolling Mean",
            "LOWESS"
        ])
        self.method_combo.setCurrentText("Savitzky-Golay")
        self.method_combo.currentTextChanged.connect(self.update_parameter_visibility)
        
        layout.addRow("Method:", self.method_combo)
        
        # Window length for Savgol and Rolling Mean
        self.window_length = QSpinBox()
        self.window_length.setRange(3, 101)
        self.window_length.setValue(11)
        self.window_length_label = layout.addRow("Window Length:", self.window_length)
        
        # Polynomial order for Savgol
        self.poly_order = QSpinBox()
        self.poly_order.setRange(1, 10)
        self.poly_order.setValue(3)
        self.poly_order_label = layout.addRow("Polynomial Order:", self.poly_order)
        
        group.setLayout(layout)
        self.update_parameter_visibility()
        return group
    
    def update_parameter_visibility(self):
        """Update parameter visibility based on selected method."""
        method = self.method_combo.currentText()
        
        # Show/hide parameters based on method
        if method == "Savitzky-Golay":
            self.window_length.setVisible(True)
            self.poly_order.setVisible(True)
        elif method == "Rolling Mean":
            self.window_length.setVisible(True)
            self.poly_order.setVisible(False)
        else:  # LOWESS
            self.window_length.setVisible(False)
            self.poly_order.setVisible(False)
    
    def preview_analysis(self):
        """Preview smoothing operation."""
        try:
            if self.dataset is None or not hasattr(self.dataset, "data") or self.dataset.data is None:
                self.preview_text.setText("No dataset available for preview.")
                return
            
            x_col = self.x_column_combo.currentText()
            y_col = self.y_column_combo.currentText()
            
            if not x_col or not y_col:
                self.preview_text.setText("Please select both X and Y columns.")
                return
            
            # Get method and parameters
            method_map = {
                "Savitzky-Golay": "savgol",
                "Rolling Mean": "rolling_mean",
                "LOWESS": "lowess"
            }
            method = method_map[self.method_combo.currentText()]
            
            # Calculate preview
            x_data = self.dataset.data[x_col]
            y_data = self.dataset.data[y_col]
            
            start_idx = self.start_index.value()
            end_idx = self.end_index.value() if self.end_index.value() != -1 else len(x_data)
            
            kwargs = {}
            if method == "savgol":
                kwargs["window_length"] = self.window_length.value()
                kwargs["polynomial_order"] = self.poly_order.value()
            elif method == "rolling_mean":
                kwargs["window"] = self.window_length.value()
            
            result = AnalysisEngine.smooth_data(
                x_data, y_data, method, start_idx, end_idx, **kwargs
            )
            
            # Display preview
            preview_text = "Smoothing Analysis Preview\n"
            preview_text += f"Method: {self.method_combo.currentText()}\n"
            preview_text += f"Data Range: {start_idx} to {end_idx}\n"
            preview_text += f"Points: {len(result.result_data)}\n\n"
            preview_text += "Statistics:\n"
            for key, value in result.statistics.items():
                preview_text += f"  {key.replace('_', ' ').title()}: {value:.6f}\n"
            
            self.preview_text.setText(preview_text)
            
        except Exception as e:
            self.preview_text.setText(f"Preview error: {str(e)}")
    
    def get_analysis_config(self) -> Dict[str, Any]:
        """Get smoothing analysis configuration."""
        config = super().get_analysis_config()
        
        # Map display name to internal method name
        method_map = {
            "Savitzky-Golay": "savgol",
            "Rolling Mean": "rolling_mean",
            "LOWESS": "lowess"
        }
        
        # Add method-specific parameters
        additional_params = {}
        method = self.method_combo.currentText()
        if method == "Savitzky-Golay":
            additional_params["window_length"] = self.window_length.value()
            additional_params["polynomial_order"] = self.poly_order.value()
        elif method == "Rolling Mean":
            additional_params["window"] = self.window_length.value()
        
        config.update({
            "analysis_type": AnalysisType.SMOOTHING.value,
            "parameters": {
                **config["parameters"],
                "method": method_map[method],
                **additional_params
            }
        })
        
        return config
