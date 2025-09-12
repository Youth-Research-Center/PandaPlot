import os
from typing import override
from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


class ExportDatasetCommand(Command):
    """
    Command to export dataset to various file formats supported by pandas.
    """

    SUPPORTED_FORMATS = {
        'CSV (Comma Separated Values)': {
            'extension': '.csv',
            'method': 'to_csv',
            'kwargs': {'index': False},
            'description': 'CSV files'
        },
        'TSV (Tab Separated Values)': {
            'extension': '.tsv',
            'method': 'to_csv',
            'kwargs': {'sep': '\t', 'index': False},
            'description': 'TSV files'
        },
        'Excel Workbook': {
            'extension': '.xlsx',
            'method': 'to_excel',
            'kwargs': {'index': False},
            'description': 'Excel files'
        },
        'JSON (Records format)': {
            'extension': '.json',
            'method': 'to_json',
            'kwargs': {'orient': 'records', 'indent': 2},
            'description': 'JSON files'
        },
        'Parquet': {
            'extension': '.parquet',
            'method': 'to_parquet',
            'kwargs': {'index': False},
            'description': 'Parquet files'
        },
        'HTML Table': {
            'extension': '.html',
            'method': 'to_html',
            'kwargs': {'index': False},
            'description': 'HTML files'
        },
        'Pickle (pandas format)': {
            'extension': '.pkl',
            'method': 'to_pickle',
            'kwargs': {},
            'description': 'Pickle files'
        }
    }

    def __init__(self, app_context: AppContext, dataset_id: str):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        
        self.dataset_id = dataset_id
        
        # Export details
        self.export_path = None
        self.export_format = None
        self.project = None
        self.dataset = None

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
            
            # Perform the export
            success = self._export_data()
            
            if success:
                self.ui_controller.show_info_message(
                    "Export Successful", 
                    f"Dataset '{self.dataset.name}' exported successfully to:\n{self.export_path}"
                )
                return True
            else:
                return False
            
        except Exception as e:
            error_msg = f"Failed to export dataset: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Export Dataset Error", error_msg)
            return False



    def _export_data(self) -> bool:
        """
        Export the dataset data to the specified path and format.
        Returns True if successful, False otherwise.
        """
        try:
            if not self.export_format or self.export_format not in self.SUPPORTED_FORMATS:
                self.logger.error(f"Unsupported export format: {self.export_format}")
                return False
            
            if not self.dataset or self.dataset.data is None or not self.export_path:
                return False
                
            format_info = self.SUPPORTED_FORMATS[self.export_format]
            method_name = format_info['method']
            method_kwargs = format_info.get('kwargs', {})
            
            # Get the export method from pandas DataFrame
            if not hasattr(self.dataset.data, method_name):
                self.logger.error(f"DataFrame does not have method: {method_name}")
                self.ui_controller.show_error_message(
                    "Export Error",
                    f"Export format '{self.export_format}' is not supported in this pandas version."
                )
                return False
            
            export_method = getattr(self.dataset.data, method_name)
            
            # Ensure directory exists
            export_dir = os.path.dirname(self.export_path)
            if export_dir and not os.path.exists(export_dir):
                os.makedirs(export_dir)
            
            # Special handling for different formats
            if method_name == 'to_excel':
                # For Excel, we might need to install openpyxl
                try:
                    export_method(self.export_path, **method_kwargs)
                except ImportError as e:
                    if 'openpyxl' in str(e):
                        self.ui_controller.show_error_message(
                            "Export Error",
                            "Excel export requires openpyxl. Please install it with:\npip install openpyxl"
                        )
                        return False
                    raise
            elif method_name == 'to_parquet':
                # For Parquet, we might need to install pyarrow or fastparquet
                try:
                    export_method(self.export_path, **method_kwargs)
                except ImportError as e:
                    if any(lib in str(e) for lib in ['pyarrow', 'fastparquet']):
                        self.ui_controller.show_error_message(
                            "Export Error",
                            "Parquet export requires pyarrow or fastparquet. Please install with:\npip install pyarrow"
                        )
                        return False
                    raise
            else:
                # Standard export
                export_method(self.export_path, **method_kwargs)
            
            self.logger.info(f"Successfully exported dataset to {self.export_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during data export: {e}", exc_info=True)
            self.ui_controller.show_error_message(
                "Export Error",
                f"Failed to export data: {str(e)}"
            )
            return False

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
        if self.export_path and self.export_format:
            return self._export_data()
        return False