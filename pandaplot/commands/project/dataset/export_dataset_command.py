import os
from typing import Any, Callable, Tuple, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.services.qtasks import TaskScheduler


class ExportDatasetCommand(Command):
    """
    Command to export dataset to various file formats supported by pandas.
    """

    SUPPORTED_FORMATS = {
        "CSV (Comma Separated Values)": {
            "extension": ".csv",
            "method": "to_csv",
            "kwargs": {"index": False},
            "description": "CSV files"
        },
        "TSV (Tab Separated Values)": {
            "extension": ".tsv",
            "method": "to_csv",
            "kwargs": {"sep": "\t", "index": False},
            "description": "TSV files"
        },
        "Excel Workbook": {
            "extension": ".xlsx",
            "method": "to_excel",
            "kwargs": {"index": False},
            "description": "Excel files"
        },
        "JSON (Records format)": {
            "extension": ".json",
            "method": "to_json",
            "kwargs": {"orient": "records", "indent": 2},
            "description": "JSON files"
        },
        "Parquet": {
            "extension": ".parquet",
            "method": "to_parquet",
            "kwargs": {"index": False},
            "description": "Parquet files"
        },
        "HTML Table": {
            "extension": ".html",
            "method": "to_html",
            "kwargs": {"index": False},
            "description": "HTML files"
        },
        "Pickle (pandas format)": {
            "extension": ".pkl",
            "method": "to_pickle",
            "kwargs": {},
            "description": "Pickle files"
        }
    }

    def __init__(self, app_context: AppContext, dataset_id: str):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.task_scheduler: TaskScheduler = app_context.get_task_scheduler()
        
        self.dataset_id = dataset_id
        
        # Export details
        self.export_path = None
        self.export_format = None
        self.project = None
        self.dataset = None
        
        # Task state
        self.is_exporting = False

    @override
    def execute(self) -> bool:
        """Execute the export dataset command."""
        try:
            self.logger.info(f"Executing ExportDatasetCommand for dataset {self.dataset_id}")
            
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Export Dataset", 
                    "Please open or create a project first."
                )
                return False
                
            self.project = self.app_state.current_project
            if not self.project:
                return False

            # Find the dataset
            found_item = self.project.find_item(self.dataset_id)
            if not found_item:
                self.ui_controller.show_error_message(
                    "Export Dataset", 
                    f"Dataset with ID '{self.dataset_id}' not found."
                )
                return False
            
            if not isinstance(found_item, Dataset):
                self.ui_controller.show_error_message(
                    "Export Dataset", 
                    "Selected item is not a dataset."
                )
                return False

            self.dataset = found_item

            # Validate dataset has data
            if self.dataset.data is None or self.dataset.data.empty:
                self.ui_controller.show_warning_message(
                    "Export Dataset", 
                    "Cannot export empty dataset."
                )
                return False

            # Get export path and format from user using UIController
            export_result = self.ui_controller.show_export_dataset_dialog(self.dataset.name)
            if not export_result:
                return False  # User cancelled
                
            self.export_path, self.export_format = export_result
            
            # Perform the export using task scheduler
            self.is_exporting = True
            
            # Show progress dialog or status
            self.ui_controller.show_info_message(
                "Export Starting", 
                f"Starting export of dataset '{self.dataset.name}' to:\n{self.export_path}"
            )
            
            # Run export in background thread
            self.task_scheduler.run_task(
                task=self._export_data_task,
                task_arguments={},
                on_result=self._on_export_result,
                on_error=self._on_export_error,
                on_finished=self._on_export_finished,
                on_progress=self._on_export_progress
            )
            
            return True  # Command initiated successfully
            
        except Exception as e:
            error_msg = f"Failed to export dataset: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Export Dataset Error", error_msg)
            return False



    def _export_data_task(self, progress_callback: Callable[[float], None], **kwargs) -> dict:
        """
        Export task function to be run in a background thread.
        Returns a dictionary with success status and any error message.
        
        Args:
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict: {'success': bool, 'error': str or None, 'path': str or None}
        """
        self.logger.debug("Starting data export task")
        try:
            if progress_callback:
                progress_callback(0.1)  # Starting export
                
            if not self.export_format or self.export_format not in self.SUPPORTED_FORMATS:
                error_msg = f"Unsupported export format: {self.export_format}"
                self.logger.error(error_msg)
                return {"success": False, "error": error_msg, "path": None}
            
            if not self.dataset or self.dataset.data is None or not self.export_path:
                return {"success": False, "error": "Missing dataset or export path", "path": None}
                
            if progress_callback:
                progress_callback(0.2)  # Validation complete
                
            format_info = self.SUPPORTED_FORMATS[self.export_format]
            method_name = format_info["method"]
            method_kwargs = format_info.get("kwargs", {})
            
            if progress_callback:
                progress_callback(0.3)  # Format info retrieved
                
            # Get the export method from pandas DataFrame
            if not hasattr(self.dataset.data, method_name):
                error_msg = f"DataFrame does not have method: {method_name}"
                self.logger.error(error_msg)
                return {"success": False, "error": f"Export format '{self.export_format}' is not supported in this pandas version.", "path": None}
            
            export_method = getattr(self.dataset.data, method_name)
            
            if progress_callback:
                progress_callback(0.4)  # Export method ready
            
            # Ensure directory exists
            export_dir = os.path.dirname(self.export_path)
            if export_dir and not os.path.exists(export_dir):
                os.makedirs(export_dir)
                
            if progress_callback:
                progress_callback(0.5)  # Directory prepared
            
            # Special handling for different formats
            if method_name == "to_excel":
                # For Excel, we might need to install openpyxl
                try:
                    export_method(self.export_path, **method_kwargs)
                except ImportError as e:
                    if "openpyxl" in str(e):
                        return {"success": False, "error": "Excel export requires openpyxl. Please install it with:\npip install openpyxl", "path": None}
                    raise
            elif method_name == "to_parquet":
                # For Parquet, we might need to install pyarrow or fastparquet
                try:
                    export_method(self.export_path, **method_kwargs)
                except ImportError as e:
                    if any(lib in str(e) for lib in ["pyarrow", "fastparquet"]):
                        return {"success": False, "error": "Parquet export requires pyarrow or fastparquet. Please install with:\npip install pyarrow", "path": None}
                    raise
            else:
                # Standard export
                export_method(self.export_path, **method_kwargs)
            
            if progress_callback:
                progress_callback(0.9)  # Export complete
            
            self.logger.info(f"Successfully exported dataset to {self.export_path}")
            
            if progress_callback:
                progress_callback(1.0)  # Finished
                
            return {"success": True, "error": None, "path": self.export_path}
            
        except Exception as e:
            error_msg = f"Error during data export: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg, "path": None}

    def _on_export_result(self, result: dict):
        """Handle successful completion of export task."""
        try:
            self.is_exporting = False
            
            if result.get("success", False):
                dataset_name = self.dataset.name if self.dataset else "Unknown"
                self.ui_controller.show_info_message(
                    "Export Successful", 
                    f"Dataset '{dataset_name}' exported successfully to:\n{result['path']}"
                )
                self.logger.info(f"Export completed successfully: {result['path']}")
            else:
                error_msg = result.get("error", "Unknown export error")
                self.ui_controller.show_error_message("Export Failed", error_msg)
                self.logger.error(f"Export failed: {error_msg}")
                
        except Exception as e:
            self.logger.error(f"Error handling export result: {e}", exc_info=True)
            self.ui_controller.show_error_message("Export Error", f"Error processing export result: {str(e)}")

    def _on_export_error(self, error_info: Tuple[Any, Any, str]):
        """Handle error during export task."""
        try:
            self.is_exporting = False
            error_type, error_value, error_traceback = error_info
            error_msg = f"Export failed with {error_type.__name__}: {str(error_value)}"
            
            self.logger.error(f"Export task error: {error_msg}")
            self.logger.error(f"Traceback: {error_traceback}")
            
            self.ui_controller.show_error_message("Export Error", error_msg)
            
        except Exception as e:
            self.logger.error(f"Error handling export error: {e}", exc_info=True)

    def _on_export_finished(self):
        """Handle completion of export task (success or failure)."""
        try:
            self.is_exporting = False
            self.logger.info("Export task finished")
            
        except Exception as e:
            self.logger.error(f"Error in export finished handler: {e}", exc_info=True)

    def _on_export_progress(self, progress: float):
        """Handle progress updates from export task."""
        try:
            # You could update a progress bar here if the UI supports it
            # For now, just log the progress
            if progress <= 1.0:
                percentage = int(progress * 100)
                self.logger.debug(f"Export progress: {percentage}%")
                
        except Exception as e:
            self.logger.error(f"Error handling export progress: {e}", exc_info=True)

    def undo(self):
        """
        Undo is not applicable for export operations.
        We could potentially delete the exported file, but that might be unexpected.
        """
        pass
    
    def redo(self):
        """
        Redo the export operation.
        """
        if self.export_path and self.export_format and not self.is_exporting:
            # Run export in background thread again
            self.is_exporting = True
            self.task_scheduler.run_task(
                task=self._export_data_task,
                task_arguments={},
                on_result=self._on_export_result,
                on_error=self._on_export_error,
                on_finished=self._on_export_finished,
                on_progress=self._on_export_progress
            )
            return True
        return False