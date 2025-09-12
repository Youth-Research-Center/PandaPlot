import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import logging

from pandaplot.models.events import FitEvents
from pandaplot.models.project.items import Dataset


class PerformFitCommand:
    def __init__(self, fit_panel):
        self.fit_results = None
        self.fit_panel = fit_panel
        self.logger = logging.getLogger(__name__)

    def get_current_data(self):
        """Get the currently selected data."""
        dataset_id = self.fit_panel.dataset_combo.currentData()
        x_column = self.fit_panel.x_column_combo.currentText()
        y_column = self.fit_panel.y_column_combo.currentText()

        if not all([dataset_id, x_column, y_column]):
            self.logger.warning("Missing dataset or columns")
            return None

        if self.fit_panel.current_project:
            dataset = self.fit_panel.current_project.find_item(dataset_id)
            if isinstance(dataset, Dataset) and dataset.data is not None:
                df = dataset.data
                if x_column in df.columns and y_column in df.columns:
                    # Remove any NaN values
                    mask = ~(pd.isna(df[x_column]) | pd.isna(df[y_column]))
                    x_data = df[x_column][mask].values
                    y_data = df[y_column][mask].values
                    return x_data, y_data

        return None

    def on_tab_changed(self, event_data):
        """Handle tab change events to update context."""
        current_tab_type = event_data.get('tab_type')
        chart_id = event_data.get('chart_id')
        dataset_id = event_data.get('dataset_id')

        # Check if current tab is a chart tab
        if current_tab_type == 'chart' and chart_id:
            # Get the chart from the project using chart_id
            project = self.fit_panel.app_context.app_state.current_project
            if project is not None:
                chart = project.find_item(chart_id)
                if chart:
                    # Load the chart into the fit panel for data analysis
                    self.fit_panel.load_chart_object(chart)
                    self.fit_panel.set_project(project)
                    self.logger.info("Fit panel context set to chart %s", chart.name)
                else:
                    self.logger.warning("Fit panel: chart id %s not found in project", chart_id)
            else:
                self.logger.warning("No current project available while switching tab")

        elif current_tab_type == 'dataset' and dataset_id:
            # For dataset tabs, provide context for data fitting
            project = self.fit_panel.app_context.app_state.current_project
            if project is not None:
                dataset = project.find_item(dataset_id)
                if dataset:
                    # Set project context for dataset access
                    self.fit_panel.set_project(project)
                    self.fit_panel.load_chart_object(None)  # Clear chart context
                    self.logger.debug("Fit panel dataset context set for dataset %s", dataset.name)
        else:
            # Clear fit panel context when no relevant tab is active
            self.fit_panel.load_chart_object(None)
            self.logger.debug("Fit panel context cleared")

    def on_dataset_changed(self):
        """Handle dataset selection change."""
        dataset_id = self.fit_panel.dataset_combo.currentData()
        if dataset_id and self.fit_panel.current_project:
            dataset = self.fit_panel.current_project.find_item(dataset_id)
            if isinstance(dataset, Dataset) and dataset.data is not None:
                columns = list(dataset.data.columns)

                # Update column combos
                self.fit_panel.x_column_combo.clear()
                self.fit_panel.y_column_combo.clear()

                for column in columns:
                    self.fit_panel.x_column_combo.addItem(column)
                    self.fit_panel.y_column_combo.addItem(column)

                # Set defaults if possible
                if len(columns) >= 2:
                    self.fit_panel.x_column_combo.setCurrentIndex(0)
                    self.fit_panel.y_column_combo.setCurrentIndex(1)
                elif len(columns) == 1:
                    self.fit_panel.x_column_combo.setCurrentIndex(0)

                # Update data points display
                self.fit_panel.update_data_points_display()




    def _get_fit_func(self, fit_type: str):
        """Get the fitting function based on the selected type."""
        if "Linear" in fit_type:
            return lambda x, a, b: a * x + b, ["a", "b"]
        elif "Quadratic" in fit_type:
            return lambda x, a, b, c: a * x ** 2 + b * x + c, ["a", "b", "c"]
        elif "Exponential" in fit_type:
            return lambda x, a, b, c: a * np.exp(b * x) + c, ["a", "b", "c"]
        elif "Power" in fit_type:
            return lambda x, a, b, c: a * (x ** b) + c, ["a", "b", "c"]
        elif "Logarithmic" in fit_type:
            return lambda x, a, b: a * np.log(x) + b, ["a", "b"]
        elif "Custom" in fit_type:
            return self._create_custom_function()
        else:
            self.logger.error("Unknown fit type: %s", fit_type)
            raise ValueError(f"Unknown fit type: {fit_type}")

    def _create_custom_function(self):
        """Create a custom fitting function from user input."""
        function_str = self.fit_panel.custom_function_edit.text().strip()
        params_str = self.fit_panel.custom_params_edit.text().strip()
        initial_str = self.fit_panel.initial_guess_edit.text().strip()  # use as predefined values, not initial guess

        if not function_str or not params_str:
            self.logger.warning("Custom function or parameters not specified")
            raise ValueError("Custom function and parameters must be specified")

        # Parse parameters
        params = [p.strip() for p in params_str.split(",")]

        # Parse initial values (fixed params)
        fixed_params = {}
        if initial_str:
            for item in initial_str.split(","):
                if "=" in item:
                    key, val = item.split("=")
                    fixed_params[key.strip()] = float(val)

        # free parameters for fit
        free_params = [p for p in params if p not in fixed_params]

        # Create function dynamically
        def custom_func(x, *free_args):
            local_vars = {"x": x, "np": np}
            # Fill in predifined fixed values
            for k, v in fixed_params.items():
                local_vars[k] = v
            # Fill in free values
            for i, p in enumerate(free_params):
                local_vars[p] = free_args[i]
            return eval(function_str, {"__builtins__": {}}, local_vars)

        return custom_func, free_params

    def perform_fit(self):
        """Perform the curve fitting."""

        # Get data
        data = self.get_current_data()
        if data is None:
            self.fit_panel.results_text.setPlainText("Please select valid data columns.")
            self.logger.debug("No valid data columns selected, get_current_data() returned None")
            return

        x_data, y_data = data

        if len(x_data) < 2:
            self.fit_panel.results_text.setPlainText("At least 2 data points are required for fitting.")
            self.logger.debug("Received %d data points, at least 2 data points are required for fitting.", len(x_data))
            return

        try:
            # Get fit function
            fit_type = self.fit_panel.fit_type_combo.currentText()
            fit_func, param_names = self._get_fit_func(fit_type)

            # Perform fit
            popt, pcov = curve_fit(fit_func, x_data, y_data, p0=[1] * len(param_names))

            # Calculate errors
            perr = np.sqrt(np.diag(pcov))

            # Calculate R-squared if requested
            r_squared = None
            if self.fit_panel.r_squared_check.isChecked():
                y_pred = fit_func(x_data, *popt)
                ss_res = np.sum((y_data - y_pred) ** 2)
                y_data_np = np.asarray(y_data)
                ss_tot = np.sum((y_data_np - np.mean(y_data_np)) ** 2)
                r_squared = 1 - (ss_res / ss_tot)

            # Generate fit data for plotting
            x_fit = np.linspace(x_data.min(), x_data.max(), self.fit_panel.fit_points_spin.value())
            y_fit = fit_func(x_fit, *popt)

            # Store results
            self.fit_results = {
                'fit_type': fit_type,
                'parameters': popt,
                'errors': perr,
                'param_names': param_names,
                'r_squared': r_squared,
                'x_fit': x_fit,
                'y_fit': y_fit,
                'x_data': x_data,
                'y_data': y_data,
                'covariance': pcov
            }

            # Display results
            self.fit_panel.display_results()

            # Enable apply button
            self.fit_panel.apply_button.setEnabled(True)

            # Publish fit completed event
            self.fit_panel.publish_event(FitEvents.FIT_COMPLETED, {
                'fit_results': self.fit_results,
                'chart_id': self.fit_panel.current_chart.id if self.fit_panel.current_chart else None,
                'fit_type': self.fit_results.get('fit_type', 'Unknown')
            })

        except Exception as e:
            self.logger.error("Fit failed: %s", str(e), exc_info=True)
            self.fit_panel.results_text.setPlainText(f"Fit failed: {str(e)}")
            self.fit_panel.equation_label.setText("Fit failed")
            self.fit_panel.apply_button.setEnabled(False)

    def format_equation(self, fit_type: str, params):
        """Format the equation string."""
        if "Linear" in fit_type:
            a, b = params
            return f"y = {a:.6g}x + {b:.6g}"
        elif "Quadratic" in fit_type:
            a, b, c = params
            return f"y = {a:.6g}x² + {b:.6g}x + {c:.6g}"
        elif "Exponential" in fit_type:
            a, b, c = params
            return f"y = {a:.6g}e^({b:.6g}x) + {c:.6g}"
        elif "Power" in fit_type:
            a, b, c = params
            return f"y = {a:.6g}x^{b:.6g} + {c:.6g}"
        elif "Logarithmic" in fit_type:
            a, b = params
            return f"y = {a:.6g}ln(x) + {b:.6g}"
        elif "Custom" in fit_type:
            function_str = self.fit_panel.custom_function_edit.text().strip()
            params_str = self.fit_panel.custom_params_edit.text().strip()
            param_names = [p.strip() for p in params_str.split(",")]

            # Substitute parameter values
            equation = function_str
            for name, value in zip(param_names, params):
                equation = equation.replace(name, f"{value:.6g}")
            return f"y = {equation}"
        else:
            return "Unknown equation"
