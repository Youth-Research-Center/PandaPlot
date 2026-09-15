from typing import Any, Dict, Optional, Type, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ChartEvents, ProjectEvents
from pandaplot.models.project.items import Chart, Dataset, Item, ItemCollection
from pandaplot.models.project.items.chart import restore_chart_state, snapshot_chart_state
from pandaplot.models.state import AppContext, AppState


class DeleteItemCommand(Command):
    """
    Generic command to delete any project item using to_dict/from_dict serialization.
    This command works with any item type that extends the Item base class.

    Also cascades to chart data series: deleting a Dataset (directly, or as
    part of deleting a Folder that contains one) would otherwise leave
    series pointing at a now-missing dataset_id -- silently stale until the
    project reloads and series-to-dataset resolution starts failing at
    render time (see resolve_series_data in chart_editor.py).
    """

    def __init__(self, app_context: AppContext, item_id: str, *, confirm: bool = True):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.item_id = item_id
        self.confirm = confirm

        # Store state for undo
        self.deleted_item_data: Optional[Dict[str, Any]] = None
        self.deleted_item_class: Optional[Type[Item]] = None
        self.parent_item: Optional[Item] = None

        # Charts whose data_series were stripped of a reference to a dataset
        # being deleted, keyed by chart_id -- captured fresh in execute()/
        # redo() (via _strip_dangling_series) so undo() can restore each
        # chart to its exact prior state.
        self._chart_snapshots: Dict[str, Dict[str, Any]] = {}

    def _dataset_ids_under(self, item: Item) -> set:
        """Every Dataset id that deleting `item` would remove: itself if
        it's a Dataset, or (recursively) any Dataset nested inside it if
        it's a collection (Folder) -- project.remove_item() cascades to
        children the same way."""
        if isinstance(item, Dataset):
            return {item.id}
        if isinstance(item, ItemCollection):
            ids: set = set()
            for child in item.get_items():
                ids |= self._dataset_ids_under(child)
            return ids
        return set()

    def _strip_dangling_series(self, project, dataset_ids: set) -> None:
        """Remove any chart data series referencing a dataset about to be
        deleted, snapshotting each affected chart first so undo() can
        restore it exactly. Recomputes from scratch every call, so it's
        safe to call again from redo() after undo() has put those series
        back."""
        self._chart_snapshots = {}
        if not dataset_ids:
            return
        for candidate in project.get_all_items():
            if not isinstance(candidate, Chart):
                continue
            if not any(series.dataset_id in dataset_ids for series in candidate.data_series):
                continue
            self._chart_snapshots[candidate.id] = snapshot_chart_state(candidate)
            candidate.data_series = [
                series for series in candidate.data_series if series.dataset_id not in dataset_ids
            ]
            candidate.update_modified_time()
            self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {"chart_id": candidate.id})

    def _restore_chart_snapshots(self, project) -> None:
        """Undo _strip_dangling_series: restore every affected chart's
        data_series (and everything else snapshot_chart_state captured) to
        what it was right before this command's execute()/redo() ran."""
        for chart_id, snapshot in self._chart_snapshots.items():
            chart = project.find_item(chart_id)
            if isinstance(chart, Chart):
                restore_chart_state(chart, snapshot)
                self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {"chart_id": chart_id})

    @override
    def execute(self) -> CommandResult:
        """Execute the delete item command."""
        try:
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.logger.warning("DeleteItemCommand.execute: no project is currently loaded")
                self.ui_controller.show_warning_message(
                    "Delete Item",
                    "No project is currently loaded."
                )
                return CommandResult.FAILURE

            project = get_current_project(self.app_context)
            if not project:
                self.logger.warning(
                    "DeleteItemCommand.execute: has_project is True but current_project is None"
                )
                return CommandResult.FAILURE

            # Find the item to delete
            item = project.find_item(self.item_id)
            if item is None:
                self.logger.warning("DeleteItemCommand.execute: item '%s' not found", self.item_id)
                self.ui_controller.show_warning_message(
                    "Delete Item",
                    f"Item '{self.item_id}' not found in the project."
                )
                return CommandResult.FAILURE

            # Store the item's class type and serialized data for undo
            self.deleted_item_class = type(item)
            self.deleted_item_data = item.to_dict()

            # Find the parent to store the relationship
            if item.parent_id:
                self.parent_item = project.find_item(item.parent_id)

            # Get item name for user confirmation
            item_name = getattr(item, "name", self.item_id)
            item_type = self.deleted_item_class.__name__.lower()

            # Confirm deletion (skipped when the caller already confirmed a
            # batch operation, e.g. bulk delete in the gallery tab)
            if self.confirm:
                response = self.ui_controller.show_question(
                    "Delete Item",
                    f"Are you sure you want to delete the {item_type} '{item_name}'?\nThis action cannot be undone."
                )
                if not response:
                    return CommandResult.FAILURE

            # Strip any chart data series referencing a dataset this delete
            # is about to remove, before it actually disappears -- otherwise
            # those series silently dangle (see class docstring).
            self._strip_dangling_series(project, self._dataset_ids_under(item))

            # Remove the item from the project
            project.remove_item(item)

            # Emit event
            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                "project": project,
                "item_id": self.item_id,
                "item_type": item_type,
                "item_name": item_name,
                "item_data": self.deleted_item_data
            })
            self.logger.info(
                "DeleteItemCommand: Deleted %s '%s' (id=%s)",
                item_type,
                item_name,
                self.item_id
            )
            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to delete item: {str(e)}"
            self.logger.error("DeleteItemCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message(
                "Delete Item Error", error_msg)
            return CommandResult.FAILURE

    def undo(self) -> CommandResult:
        """Undo the delete item command."""
        try:
            if (self.deleted_item_data is None or
                self.deleted_item_class is None or
                    not self.app_state.has_project):
                return CommandResult.FAILURE

            project = get_current_project(self.app_context)
            if not project:
                self.logger.warning(
                    "DeleteItemCommand.undo: has_project is True but current_project is None (item_id=%s)",
                    self.item_id,
                )
                return CommandResult.FAILURE

            # Recreate the item from its serialized data
            restored_item = self.deleted_item_class.from_dict(
                self.deleted_item_data)

            # Determine the parent for restoration
            parent_id = None
            if self.parent_item is not None:
                parent_id = self.parent_item.id

            # Add the item back to the project
            project.add_item(restored_item, parent_id=parent_id)

            # Restore any chart data series this delete had stripped.
            self._restore_chart_snapshots(project)

            # Get item info for logging
            item_name = getattr(restored_item, "name", self.item_id)
            item_type = self.deleted_item_class.__name__.lower()

            # Emit event
            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                "project": project,
                "item_id": self.item_id,
                "item_type": item_type,
                "item_name": item_name,
                "item": restored_item
            })
            self.logger.info(
                "DeleteItemCommand: Restored %s '%s' (id=%s)",
                item_type,
                item_name,
                self.item_id
            )
            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to undo delete item: {str(e)}"
            self.logger.error("DeleteItemCommand Undo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)
            return CommandResult.FAILURE

    def redo(self) -> CommandResult:
        """Redo the delete item command."""
        try:
            if (self.deleted_item_data is None or
                self.deleted_item_class is None or
                    not self.app_state.has_project):
                return CommandResult.FAILURE

            project = get_current_project(self.app_context)
            if not project:
                self.logger.warning(
                    "DeleteItemCommand.redo: has_project is True but current_project is None (item_id=%s)",
                    self.item_id,
                )
                return CommandResult.FAILURE

            # Find the restored item and delete it again
            item = project.find_item(self.item_id)
            if item is None:
                self.logger.warning("DeleteItemCommand.redo: item '%s' not found", self.item_id)
                return CommandResult.FAILURE

            # Strip dangling chart series again -- undo() put them back, so
            # this recomputes fresh rather than assuming last time's result
            # still applies.
            self._strip_dangling_series(project, self._dataset_ids_under(item))

            # Remove the item from the project
            project.remove_item(item)

            # Get item info for logging and events
            item_name = getattr(item, "name", self.item_id)
            item_type = self.deleted_item_class.__name__.lower()

            # Emit event
            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                "project": project,
                "item_id": self.item_id,
                "item_type": item_type,
                "item_name": item_name,
                "item_data": self.deleted_item_data
            })
            self.logger.info(
                "DeleteItemCommand: Redone deletion of %s '%s' (id=%s)",
                item_type,
                item_name,
                self.item_id
            )
            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to redo delete item: {str(e)}"
            self.logger.error("DeleteItemCommand Redo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        """Release the deleted-item snapshot and parent reference held for
        undo once this command is dropped from the stacks for good (see
        Command.cleanup)."""
        self.deleted_item_data = None
        self.deleted_item_class = None
        self.parent_item = None
        self._chart_snapshots = {}
