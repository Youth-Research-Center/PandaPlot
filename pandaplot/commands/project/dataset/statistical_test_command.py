"""
Command for running a statistical test and adding the results to the project
as a new dataset, with undo/redo support.
"""

import uuid
from typing import List, Optional, override

from pandaplot.analysis import StatsEngine, StatTestResult, StatTestType
from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state import AppContext, AppState


class StatisticalTestCommand(Command):
    """
    Runs a statistical test on the columns of a source dataset and stores the
    result as a new results dataset in the project.
    """

    def __init__(
        self,
        app_context: AppContext,
        source_dataset_id: str,
        test_type: StatTestType,
        column_names: List[str],
        alpha: float = 0.05,
        alternative: str = "two-sided",
        popmean: float = 0.0,
        *,
        equal_var: bool = True,
        result_name: Optional[str] = None,
        folder_id: Optional[str] = None,
    ):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.source_dataset_id = source_dataset_id
        self.test_type = test_type
        self.column_names = column_names
        self.alpha = alpha
        self.alternative = alternative
        self.popmean = popmean
        self.equal_var = equal_var
        self.result_name = result_name
        self.folder_id = folder_id

        # State for undo/redo.
        self.result_dataset_id: Optional[str] = None
        self.result: Optional[StatTestResult] = None

    def run_test(self) -> StatTestResult:
        """Run the test and return the result without touching the project.

        Useful for previewing results in the UI before committing them.
        """
        source = self._get_source_dataset()
        if source is None or source.data is None:
            raise ValueError("Source dataset is not available.")

        missing = [c for c in self.column_names if c not in source.data.columns]
        if missing:
            raise ValueError(f"Columns not found in dataset: {', '.join(missing)}")

        columns = [source.data[c] for c in self.column_names]
        return StatsEngine.run_test(
            self.test_type,
            columns,
            alpha=self.alpha,
            alternative=self.alternative,
            popmean=self.popmean,
            equal_var=self.equal_var,
        )

    @override
    def execute(self) -> CommandResult:
        try:
            self.logger.info("Executing StatisticalTestCommand (%s)", self.test_type.value)
            project = get_current_project(self.app_context)
            if project is None:
                message = "No project loaded; cannot run statistical test."
                self.logger.warning(message)
                self.ui_controller.show_error_message("Statistical Test Error", message)
                return CommandResult.FAILURE

            self.result = self.run_test()

            results_df = self.result.to_dataframe()
            name = self.result_name or self.result.result_name()

            self.result_dataset_id = str(uuid.uuid4())
            dataset = Dataset(
                id=self.result_dataset_id,
                name=name,
                data=results_df,
                source_file=None,
            )
            project.add_item(dataset, parent_id=self.folder_id)

            self.app_state.event_bus.emit(DatasetEvents.DATASET_CREATED, {
                "project": project,
                "dataset_id": self.result_dataset_id,
                "dataset_name": name,
                "folder_id": self.folder_id,
                "dataset_data": dataset.data,
            })

            self.logger.info("Created results dataset '%s' (%s)", name, self.result_dataset_id)
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error("Statistical test failed: %s", e, exc_info=True)
            self.ui_controller.show_error_message("Statistical Test Error", str(e))
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        try:
            project = get_current_project(self.app_context)
            if not self.result_dataset_id or project is None:
                self.logger.warning(
                    "StatisticalTestCommand.undo: cannot undo (result_dataset_id set=%s, current_project set=%s)",
                    bool(self.result_dataset_id), project is not None,
                )
                return CommandResult.FAILURE
            dataset = project.find_item(self.result_dataset_id)
            if dataset:
                project.remove_item(dataset)
                self.app_state.event_bus.emit(DatasetEvents.DATASET_DELETED, {
                    "project": project,
                    "dataset_id": self.result_dataset_id,
                    "dataset_name": dataset.name,
                })
            self.logger.info("Undone statistical test results dataset '%s'", self.result_dataset_id)
            return CommandResult.SUCCESS
        except Exception as e:
            self.logger.error("Failed to undo statistical test: %s", e, exc_info=True)
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the created-dataset id and test-result snapshot held for
        undo once this command is dropped from the stacks for good (see
        Command.cleanup)."""
        self.result_dataset_id = None
        self.result = None

    def _get_source_dataset(self) -> Optional[Dataset]:
        project = get_current_project(self.app_context)
        if not project:
            return None
        item = project.find_item(self.source_dataset_id)
        if isinstance(item, Dataset):
            return item
        return None
