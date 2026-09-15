from typing import Optional

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget

# TODO(#220): ui controller should be a facade for all UI-related interactions
# This allows us to keep UI logic separate from business logic in the MVC pattern.
# It can handle dialogs, notifications, and other user interactions.


class UIController:
    """
    UI Controller that handles user interface interactions like dialogs.
    This separates UI logic from business logic in the MVC pattern.
    """
    
    def __init__(self, parent_widget: Optional[QWidget] = None):
        self.parent_widget = parent_widget
    
    def show_open_project_dialog(self) -> Optional[str]:
        """
        Show file dialog to open a project file.
        
        Returns:
            str: Selected file path, or None if cancelled
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent_widget,
            "Open Project",
            "",
            "Project files (*.pplot);;JSON files (*.json);;All files (*.*)"
        )
        
        return file_path if file_path else None
    
    def show_save_project_dialog(self, default_name: str = "untitled.pplot") -> Optional[str]:
        """
        Show file dialog to save a project file.
        
        Args:
            default_name (str): Default filename
            
        Returns:
            str: Selected file path, or None if cancelled
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent_widget,
            "Save Project",
            default_name,
            "Project files (*.pplot);;JSON files (*.json);;All files (*.*)"
        )
        
        return file_path if file_path else None
    
    def show_new_project_dialog(self, default_name: str = "New Project") -> Optional[str]:
        """
        Prompt for a name for a brand-new project.

        Args:
            default_name (str): Name pre-filled in the input field.

        Returns:
            str: The entered name (whitespace-trimmed), or None if the user
                cancelled or entered a blank name.
        """
        name, ok = QInputDialog.getText(
            self.parent_widget,
            "New Project",
            "Project name:",
            text=default_name,
        )
        name = name.strip() if name else ""
        return name if ok and name else None

    def show_import_data_dialog(self) -> Optional[str]:
        """
        Show file dialog to import a data file (CSV/TSV or single-sheet Excel workbook).

        Returns:
            str: Selected file path, or None if cancelled
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent_widget,
            "Import Data File",
            "",
            "Data files (*.csv *.txt *.tsv *.xlsx *.xls);;"
            "CSV files (*.csv *.txt *.tsv);;"
            "Excel files (*.xlsx *.xls);;"
            "All files (*.*)"
        )

        return file_path if file_path else None

    def show_error_message(self, title: str, message: str):
        """
        Show an error message dialog.
        
        Args:
            title (str): Dialog title
            message (str): Error message
        """
        QMessageBox.critical(self.parent_widget, title, message)
    
    def show_warning_message(self, title: str, message: str):
        """
        Show a warning message dialog.
        
        Args:
            title (str): Dialog title
            message (str): Warning message
        """
        QMessageBox.warning(self.parent_widget, title, message)
    
    def show_info_message(self, title: str, message: str):
        """
        Show an information message dialog.
        
        Args:
            title (str): Dialog title
            message (str): Information message
        """
        QMessageBox.information(self.parent_widget, title, message)
    
    def show_question(self, title: str, message: str) -> bool:
        """
        Show a yes/no question dialog.
        
        Args:
            title (str): Dialog title
            message (str): Question message
            
        Returns:
            bool: True if user clicked Yes, False if No
        """
        reply = QMessageBox.question(
            self.parent_widget,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes
    
    def show_confirmation(self, title: str, message: str, details: str|None = None) -> bool:
        """
        Show a confirmation dialog with optional details.
        
        Args:
            title (str): Dialog title
            message (str): Main message
            details (str, optional): Detailed information
            
        Returns:
            bool: True if user confirmed, False otherwise
        """
        msg_box = QMessageBox(self.parent_widget)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        if details:
            msg_box.setDetailedText(details)
        
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
        
        reply = msg_box.exec()
        return reply == QMessageBox.StandardButton.Ok

    def show_action_or_cancel(self, title: str, message: str, action_label: str) -> bool:
        """
        Show a warning-style dialog with one custom action button plus Cancel.

        Args:
            title (str): Dialog title
            message (str): Message explaining what the action would do
            action_label (str): Label for the custom action button

        Returns:
            bool: True if the action button was clicked, False for Cancel
                (or the dialog being dismissed via Esc/titlebar).
        """
        box = QMessageBox(QMessageBox.Icon.Warning, title, message, parent=self.parent_widget)
        action_button = box.addButton(action_label, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        return box.clickedButton() is action_button

    def get_text_input(self, title: str, message: str, default_text: str = "") -> Optional[str]:
        """
        Show a text input dialog.
        
        Args:
            title (str): Dialog title
            message (str): Input prompt message
            default_text (str): Default text to show in input field
            
        Returns:
            str: User input text, or None if cancelled
        """
        text, ok = QInputDialog.getText(self.parent_widget, title, message, text=default_text)
        return text if ok else None
    

    def show_export_dataset_dialog(self, dataset_name: str) -> Optional[tuple[str, str]]:
        """
        Show file dialog to export dataset with format selection.
        
        Args:
            dataset_name (str): Name of the dataset being exported
            
        Returns:
            tuple[str, str]: (file_path, selected_format) or None if cancelled
        """
        # Define supported formats with their filters
        formats = {
            "CSV (Comma Separated Values) (*.csv)": ("CSV (Comma Separated Values)", ".csv"),
            "TSV (Tab Separated Values) (*.tsv)": ("TSV (Tab Separated Values)", ".tsv"),
            "Excel Workbook (*.xlsx)": ("Excel Workbook", ".xlsx"),
            "JSON (Records format) (*.json)": ("JSON (Records format)", ".json"),
            "Parquet (*.parquet)": ("Parquet", ".parquet"),
            "HTML Table (*.html)": ("HTML Table", ".html"),
            "Pickle (pandas format) (*.pkl)": ("Pickle (pandas format)", ".pkl")
        }
        
        # Create filter string
        filter_parts = list(formats.keys())
        all_filters = ";;".join(filter_parts)
        
        # Show save file dialog
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self.parent_widget,
            f"Export {dataset_name}",
            f"{dataset_name}.csv",  # Default to CSV
            all_filters
        )
        
        if file_path and selected_filter:
            # Get the format name from the selected filter
            format_name, extension = formats.get(selected_filter, ("CSV (Comma Separated Values)", ".csv"))
            
            # Ensure the file has the correct extension
            if not file_path.lower().endswith(extension.lower()):
                file_path += extension
                
            return file_path, format_name
        
        return None

    def set_parent_widget(self, parent_widget: QWidget):
        """Set the parent widget for dialogs."""
        self.parent_widget = parent_widget
