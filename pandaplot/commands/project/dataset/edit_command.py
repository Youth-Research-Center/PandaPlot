from typing import Tuple, override

from pandaplot.commands.project.dataset.dataset_command import DatasetCommand
from pandaplot.models.events.event_data import DatasetDataChangedData
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.state.app_context import AppContext


class EditCommand(DatasetCommand):
    def __init__(self, app_context: AppContext, dataset_id: str, index: Tuple[int, int], old_value, new_value):
        super().__init__(app_context, dataset_id)

        self.index = index
        self.new_value = new_value
        self.old_value = old_value

    @override
    def execute(self) -> bool:
        try:
            self.logger.info("Executing EditCommand")
            if not self._validate_and_get_dataset("Edit Cell"):
                return False

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
        