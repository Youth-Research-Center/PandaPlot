from copy import deepcopy
from typing import Any, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Item, ItemCollection
from pandaplot.models.state import AppContext, AppState


class DeleteItemCommand(Command):
    """
    Generic command to delete a project item, retaining collection subtrees for undo.
    This command works with any item type that extends the Item base class.

    Also cascades to any item that references something being deleted (directly,
    or as part of deleting a Folder that contains it) via Item.on_items_removed --
    e.g. a Chart's data_series referencing a Dataset. This command has no
    knowledge of which item types have dependencies or what those dependencies
    look like; that lives entirely on the dependent item's own class.
    """

    def __init__(self, app_context: AppContext, item_id: str, *, confirm: bool = True):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.item_id = item_id
        self.confirm = confirm

        # Store state for undo
        self.deleted_item_data: dict[str, Any] | None = None
        self.deleted_item_class: type[Item] | None = None
        self._deleted_collection: ItemCollection | None = None
        self.parent_item: Item | None = None
        self._deleted_index: int | None = None

        # Items whose on_items_removed() hook fired because they referenced
        # something being deleted, keyed by item id -- captured fresh in
        # execute()/redo() (via _apply_dependency_cleanup) so undo() can
        # restore each one to its exact prior state.
        self._snapshots: dict[str, Any] = {}

    def _collect_ids_under(self, item: Item) -> set:
        """item.id plus, recursively, every child id if item is a Folder --
        project.remove_item() cascades to children the same way."""
        ids = {item.id}
        if isinstance(item, ItemCollection):
            for child in item.get_items():
                ids |= self._collect_ids_under(child)
        return ids

    def _apply_dependency_cleanup(self, project, removed_ids: set) -> None:
        """Call on_items_removed() on every item whose class has ever
        overridden referenced_item_ids(), snapshotting each one that was
        actually affected so undo() can restore it exactly. Recomputes
        from scratch every call, so it's safe to call again from redo()
        after undo() has put those references back."""
        self._snapshots = {}
        dependency_classes = tuple(Item._dependency_aware_classes)
        if not dependency_classes:
            return
        # Not atomic: if on_items_removed() raises partway through, items
        # already stripped before the exception are not rolled back. Accepted
        # since execute() returning FAILURE means this command never reaches
        # the undo stack anyway.
        for other in project.get_all_items():
            if other.id in removed_ids or not isinstance(other, dependency_classes):
                continue
            snapshot = other.on_items_removed(removed_ids)
            if snapshot is not None:
                self._snapshots[other.id] = snapshot
                self._emit_dependency_update_event(other)

    def _restore_dependency_cleanup(self, project) -> None:
        """Undo _apply_dependency_cleanup: restore every affected item to
        what it was right before this command's execute()/redo() ran."""
        for item_id, snapshot in self._snapshots.items():
            item = project.find_item(item_id)
            if item is not None:
                item.restore_removed_items_snapshot(snapshot)
                self._emit_dependency_update_event(item)

    def _sibling_index(self, project, item: Item) -> int | None:
        """Position of `item` among its siblings, so undo() can put it back."""
        parent = project.find_item(item.parent_id) if item.parent_id else project.root
        if not isinstance(parent, ItemCollection):
            return None
        keys = list(parent.items.keys())
        return keys.index(item.id) if item.id in keys else None

    def _subtree_intact(self, project, item: Item, subtree_ids: set) -> bool:
        """True if `item` is still attached and every id in its subtree is
        still indexed, i.e. a failed removal changed nothing."""
        return project.find_item(item.id) is item and all(project.find_item(i) is not None for i in subtree_ids)

    def _remove_with_rollback(self, project, item: Item) -> None:
        """Remove `item`; if that raises, undo the dependency cascade already
        applied so no dependent is left stripped, then re-raise."""
        try:
            project.remove_item(item)
        except Exception:
            self._restore_dependency_cleanup(project)
            self._snapshots = {}
            raise

    def _descendant_removal_payloads(self, item: Item) -> list[dict[str, Any]]:
        """PROJECT_ITEM_REMOVED payloads (without `project`) for every item
        nested under `item`, deepest first. project.remove_item() drops the
        whole subtree, so subscribers keyed on item_id (e.g. the tab closer)
        must hear about each descendant, not only the collection."""
        payloads: list[dict[str, Any]] = []
        if isinstance(item, ItemCollection):
            for child in item.get_items():
                payloads.extend(self._descendant_removal_payloads(child))
                payloads.append({
                    "item_id": child.id,
                    "item_type": type(child).__name__.lower(),
                    "item_name": getattr(child, "name", child.id),
                    "item_data": child.to_dict(),
                })
        return payloads

    def _emit_removed_events(self, project, descendants: list[dict[str, Any]], payload: dict[str, Any]) -> None:
        """Emit PROJECT_ITEM_REMOVED for each removed descendant, then for the
        deleted item itself."""
        for descendant in descendants:
            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {"project": project, **descendant})
        self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {"project": project, **payload})

    def _emit_dependency_update_event(self, item: Item) -> None:
        event = item.dependency_update_event()
        if event is not None:
            name, payload = event
            self.app_context.event_bus.emit(name, payload)

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

            item_class = type(item)
            parent_item = project.find_item(item.parent_id) if item.parent_id else None

            # Get item name for user confirmation
            item_name = getattr(item, "name", self.item_id)
            item_type = item_class.__name__.lower()

            # Confirm deletion (skipped when the caller already confirmed a
            # batch operation, e.g. bulk delete in the gallery tab)
            if self.confirm:
                response = self.ui_controller.show_question(
                    "Delete Item",
                    f"Are you sure you want to delete the {item_type} '{item_name}'?"
                )
                if not response:
                    return CommandResult.FAILURE

            # Cascade to any item referencing something this delete is
            # about to remove, before it actually disappears -- otherwise
            # those references silently dangle (see class docstring).
            # to_dict omits child types and in-memory dataset/image payloads, so
            # collections also keep a detached subtree snapshot for undo. Undo
            # state is only stored once the delete has actually succeeded.
            item_data = item.to_dict()
            collection_snapshot = deepcopy(item) if isinstance(item, ItemCollection) else None
            sibling_index = self._sibling_index(project, item)
            descendants = self._descendant_removal_payloads(item)
            self._apply_dependency_cleanup(project, self._collect_ids_under(item))

            # Remove the item from the project
            self._remove_with_rollback(project, item)

            self._deleted_index = sibling_index
            self.deleted_item_class = item_class
            self.deleted_item_data = item_data
            self._deleted_collection = collection_snapshot
            self.parent_item = parent_item

            # Emit event
            self._emit_removed_events(project, descendants, {
                "item_id": self.item_id,
                "item_type": item_type,
                "item_name": item_name,
                "item_data": self.deleted_item_data,
            })
            self.logger.info(
                "DeleteItemCommand: Deleted %s '%s' (id=%s)",
                item_type,
                item_name,
                self.item_id
            )
            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to delete item: {e!s}"
            self.logger.exception("DeleteItemCommand Error: %s", error_msg)
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

            # Restore a fresh snapshot, or deserialize a standalone item
            restored_item = (
                deepcopy(self._deleted_collection)
                if self._deleted_collection is not None
                else self.deleted_item_class.from_dict(self.deleted_item_data)
            )

            # Determine the parent for restoration
            parent_id = None
            if self.parent_item is not None:
                parent_id = self.parent_item.id

            # Add the item back to the project
            project.add_item(restored_item, parent_id=parent_id, index=self._deleted_index)

            # Restore any items this delete had cascaded into.
            self._restore_dependency_cleanup(project)

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
            error_msg = f"Failed to undo delete item: {e!s}"
            self.logger.exception("DeleteItemCommand Undo Error: %s", error_msg)
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

            # Re-snapshot the item as it is now, before the cascade touches
            # anything (as execute() does), so a later undo restores the
            # state at redo time rather than at the original delete.
            item_data = item.to_dict()
            collection_snapshot = deepcopy(item) if isinstance(item, ItemCollection) else None
            sibling_index = self._sibling_index(project, item)
            descendants = self._descendant_removal_payloads(item)

            # Re-run the dependency cascade -- undo() put those references
            # back, so this recomputes fresh rather than assuming last
            # time's result still applies.
            self._apply_dependency_cleanup(project, self._collect_ids_under(item))

            # Remove the item from the project
            subtree_ids = self._collect_ids_under(item)
            try:
                self._remove_with_rollback(project, item)
            except Exception as remove_error:
                if not self._subtree_intact(project, item, subtree_ids):
                    raise
                # Nothing was removed and dependents are restored, so report
                # ABORTED: the command stays on the redo stack instead of
                # moving to the undo stack and replaying over a live item.
                self.logger.exception("DeleteItemCommand: redo aborted, removal failed (id=%s)", self.item_id)
                self.ui_controller.show_error_message("Redo Error", f"Failed to redo delete item: {remove_error!s}")
                return CommandResult.ABORTED
            self.deleted_item_data = item_data
            self._deleted_index = sibling_index
            self._deleted_collection = collection_snapshot

            # Get item info for logging and events
            item_name = getattr(item, "name", self.item_id)
            item_type = self.deleted_item_class.__name__.lower()

            # Emit event
            self._emit_removed_events(project, descendants, {
                "item_id": self.item_id,
                "item_type": item_type,
                "item_name": item_name,
                "item_data": self.deleted_item_data,
            })
            self.logger.info(
                "DeleteItemCommand: Redone deletion of %s '%s' (id=%s)",
                item_type,
                item_name,
                self.item_id
            )
            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to redo delete item: {e!s}"
            self.logger.exception("DeleteItemCommand Redo Error: %s", error_msg)
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
        self._snapshots = {}
        self._deleted_collection = None
        self._deleted_index = None
