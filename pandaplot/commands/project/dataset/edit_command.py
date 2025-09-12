from typing import Tuple, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_data import DatasetDataChangedData
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext


class EditCommand(Command):
    def __init__(self, app_context: AppContext, dataset_id: str, index: Tuple[int, int], old_value, new_value):
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.dataset_id = dataset_id
        self.index = index
        self.new_value = new_value
        self.old_value = old_value

    @override
    def execute(self) -> bool:
        try:
            self.logger.info("Executing EditCommand")
            if not self.app_context.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Edit Cell", 
                    "Please open or create a project first."
                )
                return False
                
            self.project = self.app_context.app_state.current_project
            if not self.project:
                return False

            # Find the dataset
            found_item = self.project.find_item(self.dataset_id)
            if not found_item:
                self.ui_controller.show_error_message(
                    "Edit Cell", 
                    f"Dataset with ID '{self.dataset_id}' not found."
                )
                return False
            
            if not isinstance(found_item, Dataset):
                self.ui_controller.show_error_message(
                    "Edit Cell", 
                    "Selected item is not a dataset."
                )
                return False

            self.dataset = found_item

            # Get current data
            if self.dataset.data is None:
                self.ui_controller.show_warning_message(
                    "Edit Cell", 
                    "Cannot edit cell in dataset without structure."
                )
                return False
            
            self.dataset.data.iloc[self.index[0], self.index[1]] = self.new_value
            self.app_context.event_bus.emit(DatasetEvents.DATASET_DATA_CHANGED, DatasetDataChangedData(
                    dataset_id=self.dataset_id,
                    start_index=(self.index[0], self.index[1]),
                    end_index=(self.index[0], self.index[1])
                ).to_dict())
            return True
        except Exception as e:
            error_msg = f"Failed to edit cell at index: {self.index} {str(e)}"
            self.logger.error(error_msg)
            self.ui_controller.show_error_message("Edit Error", error_msg)
            return False

    def undo(self):
        self.dataset.data.iloc[self.index[0], self.index[1]] = self.old_value
        self.app_context.event_bus.emit(DatasetEvents.DATASET_DATA_CHANGED, DatasetDataChangedData(
                    dataset_id=self.dataset_id,
                    start_index=(self.index[0], self.index[1]),
                    end_index=(self.index[0], self.index[1])
                ).to_dict())
    
    def redo(self):
        self.dataset.data.iloc[self.index[0], self.index[1]] = self.new_value
        self.app_context.event_bus.emit(DatasetEvents.DATASET_DATA_CHANGED, DatasetDataChangedData(
                    dataset_id=self.dataset_id,
                    start_index=(self.index[0], self.index[1]),
                    end_index=(self.index[0], self.index[1])
                ).to_dict())
        