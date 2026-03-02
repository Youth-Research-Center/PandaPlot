"""Base command class for dataset operations with shared validation logic."""

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


class DatasetCommand(Command):
    """Base class for commands that operate on a dataset.

    Provides common initialization (app_context, app_state, ui_controller,
    dataset_id) and two dataset-resolution helpers:

    - ``_validate_and_get_dataset(command_name)`` – full validation with UI
      messages shown to the user.  Sets ``self.project`` and ``self.dataset``.
    - ``_resolve_dataset()`` – lightweight resolution that only logs on
      failure (no UI).  Returns the Dataset or None.
    """

    def __init__(self, app_context: AppContext, dataset_id: str):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.dataset_id = dataset_id
        self.project = None
        self.dataset: Dataset | None = None

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_and_get_dataset(self, command_name: str) -> bool:
        """Validate project/dataset state and populate *self.project* / *self.dataset*.

        Shows warning/error dialogs via ``ui_controller`` when validation
        fails.  Returns True on success.
        """
        if not self.app_state.has_project:
            self.ui_controller.show_warning_message(
                command_name,
                "Please open or create a project first.",
            )
            return False

        self.project = self.app_state.current_project
        if not self.project:
            return False

        found_item = self.project.find_item(self.dataset_id)
        if not found_item:
            self.ui_controller.show_error_message(
                command_name,
                f"Dataset with ID '{self.dataset_id}' not found.",
            )
            return False

        if not isinstance(found_item, Dataset):
            self.ui_controller.show_error_message(
                command_name,
                "Selected item is not a dataset.",
            )
            return False

        self.dataset = found_item
        return True

    def _resolve_dataset(self) -> Dataset | None:
        """Lightweight dataset resolution without UI messages."""
        try:
            if self.app_state.has_project and self.app_state.current_project:
                item = self.app_state.current_project.find_item(self.dataset_id)
                if item and isinstance(item, Dataset):
                    return item
            return None
        except Exception as e:
            self.logger.error(f"Error resolving dataset: {e}")
            return None
