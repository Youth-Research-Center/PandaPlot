"""Create a grouped measurement-summary dataset and persist its column roles."""

import uuid
from collections import OrderedDict
from collections.abc import Mapping
from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.chart.series_xy import unique_sibling_name
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items.column_role import ColumnRole
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.item import ItemCollection
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState
from pandaplot.services.measurement_analysis import MeasurementAnalysisService


class AnalyzeMeasurementsCommand(Command):
    """Add grouped summary results and save the selected roles on their dataset."""

    def __init__(
        self,
        app_context: AppContext,
        source_dataset_id: str,
        roles: Mapping[str, ColumnRole | str],
        *,
        measurement_groups: Mapping[str, str] | None = None,
        result_name: str | None = None,
        folder_id: str | None = None,
    ):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.source_dataset_id = source_dataset_id
        self.roles = OrderedDict(roles)
        self.measurement_groups = OrderedDict(measurement_groups) if measurement_groups is not None else None
        self.result_name = result_name
        self.folder_id = folder_id

        self.result_dataset_id: str | None = None
        self._dataset: Dataset | None = None
        self._original_roles: OrderedDict[str, ColumnRole] | None = None
        self._original_measurement_groups: OrderedDict[str, str] | None = None
        self._parent_id: str | None = folder_id
        self._result_index: int | None = None

    @override
    def execute(self) -> CommandResult:
        project = get_current_project(self.app_context)
        if project is None:
            return self._fail("No project loaded; cannot analyze measurements.")

        source = project.find_item(self.source_dataset_id)
        if not isinstance(source, Dataset):
            return self._fail("The source dataset is not available.")

        if self._dataset is not None:
            return CommandResult.NOOP

        try:
            measurement_groups = self._effective_measurement_groups(source)
            result = MeasurementAnalysisService.summarize(
                source,
                self.roles,
                measurement_groups=measurement_groups,
            )
            self._parent_id = self.folder_id if self.folder_id is not None else source.parent_id
            base_name = self.result_name or f"{source.name} - Measurement Summary"
            name = unique_sibling_name(project, self._parent_id, base_name)
            dataset = Dataset(
                id=str(uuid.uuid4()),
                name=name,
                data=result.table,
                source_file=None,
            )
            old_roles = OrderedDict(source.column_roles)
            old_groups = OrderedDict(source.column_measurement_groups)
            self._add_result(
                project,
                source,
                dataset,
                old_roles,
                old_groups,
                measurement_groups,
                index=None,
            )
            self._dataset = dataset
            self.result_dataset_id = dataset.id
            self._original_roles = old_roles
            self._original_measurement_groups = old_groups
            return CommandResult.SUCCESS
        except Exception as error:
            self.logger.exception("Failed to analyze measurements")
            self.ui_controller.show_error_message("Measurement Analysis Error", str(error))
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        project = get_current_project(self.app_context)
        source = project.find_item(self.source_dataset_id) if project is not None else None
        dataset = project.find_item(self.result_dataset_id) if project is not None and self.result_dataset_id else None
        if (
            project is None
            or not isinstance(source, Dataset)
            or not isinstance(dataset, Dataset)
            or self._original_roles is None
            or self._original_measurement_groups is None
        ):
            return CommandResult.ABORTED

        parent = project.root if dataset.parent_id in (None, project.root.id) else project.find_item(dataset.parent_id)
        if not isinstance(parent, ItemCollection):
            return CommandResult.ABORTED
        index = list(parent.items).index(dataset.id)
        current_roles = OrderedDict(source.column_roles)
        current_groups = OrderedDict(source.column_measurement_groups)
        try:
            source.set_column_roles(self._original_roles)
            source.set_column_measurement_groups(self._original_measurement_groups)
            project.remove_item(dataset)
            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                "project": project,
                "item_id": dataset.id,
                "item_type": "dataset",
                "item_name": dataset.name,
            })
            self._result_index = index
            return CommandResult.SUCCESS
        except Exception:
            self.logger.exception("Failed to undo measurement analysis")
            if project.find_item(dataset.id) is None:
                project.add_item(dataset, parent_id=self._parent_id, index=index)
            source.set_column_roles(current_roles)
            source.set_column_measurement_groups(current_groups)
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        project = get_current_project(self.app_context)
        source = project.find_item(self.source_dataset_id) if project is not None else None
        if project is None or not isinstance(source, Dataset) or self._dataset is None:
            return CommandResult.ABORTED
        if (
            project.find_item(self._dataset.id) is not None
            or self._original_roles is None
            or self._original_measurement_groups is None
        ):
            return CommandResult.ABORTED

        try:
            self._add_result(
                project,
                source,
                self._dataset,
                OrderedDict(source.column_roles),
                OrderedDict(source.column_measurement_groups),
                self._effective_measurement_groups(source),
                index=self._result_index,
            )
            return CommandResult.SUCCESS
        except Exception as error:
            self.logger.exception("Failed to redo measurement analysis")
            self.ui_controller.show_error_message("Measurement Analysis Error", str(error))
            return CommandResult.FAILURE

    def _add_result(
        self,
        project: Project,
        source: Dataset,
        dataset: Dataset,
        old_roles: OrderedDict[str, ColumnRole],
        old_groups: OrderedDict[str, str],
        measurement_groups: OrderedDict[str, str],
        *,
        index: int | None,
    ) -> None:
        """Apply role metadata and add the result as one compensating operation."""
        try:
            source.set_column_roles(self.roles)
            source.set_column_measurement_groups(measurement_groups)
            project.add_item(dataset, parent_id=self._parent_id, index=index)
            reported_folder_id = (
                self._parent_id
                if (
                    self._parent_id is not None
                    and self._parent_id != project.root.id
                    and project.find_item(self._parent_id) is not None
                )
                else None
            )
            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                "project": project,
                "item_id": dataset.id,
                "item_type": "dataset",
                "item_name": dataset.name,
                "item": dataset,
                "folder_id": reported_folder_id,
            })
        except Exception:
            if project.find_item(dataset.id) is dataset:
                project.remove_item(dataset)
            source.set_column_roles(old_roles)
            source.set_column_measurement_groups(old_groups)
            raise

    def _effective_measurement_groups(self, source: Dataset) -> OrderedDict[str, str]:
        """Resolve user selections and retain saved/default names for measured columns."""
        groups: OrderedDict[str, str] = OrderedDict()
        for column_id, role in self.roles.items():
            if ColumnRole(role) is not ColumnRole.MEASURED:
                continue
            column_name = source.column_name(column_id)
            if column_name is None:
                continue
            group_name = (
                self.measurement_groups.get(column_id)
                if self.measurement_groups is not None
                else None
            )
            group_name = group_name or source.column_measurement_groups.get(column_id) or column_name
            groups[column_id] = group_name
        return groups

    def _fail(self, message: str) -> CommandResult:
        self.logger.warning(message)
        self.ui_controller.show_error_message("Measurement Analysis Error", message)
        return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        self.result_dataset_id = None
        self._dataset = None
        self._original_roles = None
        self._original_measurement_groups = None
        self._result_index = None
