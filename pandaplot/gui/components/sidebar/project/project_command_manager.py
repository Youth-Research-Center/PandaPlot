import logging

from PySide6.QtCore import Qt

from pandaplot.commands.project.chart.create_chart_command import CreateChartCommand
from pandaplot.commands.project.dataset import ImportCsvCommand
from pandaplot.commands.project.dataset.create_empty_dataset_command import (
    CreateEmptyDatasetCommand,
)
from pandaplot.commands.project.folder import CreateFolderCommand
from pandaplot.commands.project.item import DeleteItemCommand
from pandaplot.commands.project.note import CreateNoteCommand
from pandaplot.models.events.event_data import TabOpenRequestedData
from pandaplot.models.events.event_types import UIEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext


class ProjectPanelCommandManager:
    def __init__(self,
                 app_context: AppContext,
                 get_target_folder_id,
                 get_current_item,
                 get_selected_item_info,
                 edit_item):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app_context = app_context
        self.app_state = app_context.get_app_state()
        self.get_target_folder_id = get_target_folder_id
        self.get_current_item = get_current_item
        self.get_selected_item_info = get_selected_item_info
        self.edit_item = edit_item

    def add_folder(self):
        """Add a new folder."""
        if not self.app_state.has_project:
            return

        folder_id = self.get_target_folder_id()

        command = CreateFolderCommand(self.app_context, parent_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def add_note(self):
        """Add a new note."""
        if not self.app_state.has_project:
            return

        folder_id = self.get_target_folder_id()

        command = CreateNoteCommand(self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def import_csv(self):
        """Import a CSV file as a dataset."""
        if not self.app_state.has_project:
            return

        folder_id = self.get_target_folder_id()

        command = ImportCsvCommand(self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def create_empty_dataset(self):
        """Create a new empty dataset."""
        if not self.app_state.has_project:
            return

        folder_id = self.get_target_folder_id()

        command = CreateEmptyDatasetCommand(
            self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def create_chart_from_dataset(self):
        """Create a chart from the selected dataset."""
        selected_item = self.get_current_item()
        if not selected_item:
            return

        # Get dataset information
        item_data = selected_item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data or item_data.get("type") != "dataset":
            return

        dataset_id = item_data.get("id")
        dataset_obj: Dataset = item_data.get("data")
        dataset_name = dataset_obj.name if dataset_obj else "Dataset"
        chart_name = f"Chart from {dataset_name}"

        command = CreateChartCommand(self.app_context, dataset_id, chart_name, dataset_obj.parent_id)
        self.app_context.get_command_executor().execute_command(command)

    def rename_selected_item(self):
        """Rename the selected item by starting inline editing."""
        selected_info = self.get_selected_item_info()
        if not selected_info or selected_info["type"] == "project":
            return

        # Start inline editing on the current item
        current_item = selected_info["item"]
        if current_item:
            # Start editing the first column (name)
            self.edit_item(current_item, 0)

    def delete_selected_item(self):
        """Delete the selected item."""
        selected_info = self.get_selected_item_info()
        if not selected_info or selected_info["type"] == "project":
            return

        item_id = selected_info["id"]
        command = DeleteItemCommand(self.app_context, item_id)
        self.app_context.get_command_executor().execute_command(command)

    def open_selected_item(self):
        """Open the selected item."""
        current_item = self.get_current_item()
        if not current_item:
            return

        item_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        item_type = item_data.get("type", "")
        item_id = item_data.get("id", "")

        # Handle different item types
        if item_type == "folder":
            # Toggle folder expansion
            current_item.setExpanded(not current_item.isExpanded())
        else:
            item = item_data.get("data")
            item_name = item.name if item else "Unnamed Item"

            if self.app_state:
                self.app_state.event_bus.emit(UIEvents.TAB_OPEN_REQUESTED, TabOpenRequestedData(
                    item_id=item_id,
                    item_name=item_name
                ).to_dict())

    def on_item_double_clicked(self, item, column):
        """Handle double-click on tree item."""
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        if item_data:
            item_type = item_data.get("type", "")

            # For folders, toggle expansion
            if item_type == "folder":
                item.setExpanded(not item.isExpanded())
            # For other items that can be opened, don't start editing
            elif item_type in ["note", "dataset", "chart"]:
                self.open_selected_item()
                return

        # For project root or items without actions, do nothing
        # Inline editing is triggered by single click when item is selected
