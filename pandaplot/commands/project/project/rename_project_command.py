"""Command for renaming the current project itself (not a project tree item)."""

from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


class RenameProjectCommand(Command):
    """Rename the current project.

    Unlike RenameItemCommand, this targets `Project.name` directly - the
    project root is not an `Item` reachable via `Project.find_item`.
    """

    def __init__(self, app_context: AppContext, new_name: str):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.new_name = new_name.strip()
        self.old_name: str | None = None
        self._applied: bool = False
        self._project: Project | None = None

    @override
    def execute(self) -> CommandResult:
        try:
            project = get_current_project(self.app_context)
            if project is None:
                self.logger.warning(
                    "RenameProjectCommand.execute: cannot rename to '%s', no project is loaded",
                    self.new_name,
                )
                self.ui_controller.show_warning_message(
                    "Rename Project", "Please open or create a project first.")
                return CommandResult.FAILURE

            self.old_name = project.name
            if not self.new_name:
                self.logger.warning(
                    "RenameProjectCommand.execute: rejected empty new name for project '%s'",
                    self.old_name,
                )
                self.ui_controller.show_error_message(
                    "Rename Project", "Project name cannot be empty.")
                return CommandResult.FAILURE
            if self.new_name == self.old_name:
                return CommandResult.NOOP

            self._apply_rename(project, self.new_name)
            self._project = project
            self._applied = True
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.exception("Failed to rename project")
            self.ui_controller.show_error_message("Rename Project Error", "Couldn't rename the project.", error=e)
            return CommandResult.FAILURE

    def _apply_rename(self, project: Project, name: str) -> None:
        project.name = name
        self.app_context.event_bus.emit(
            ProjectEvents.PROJECT_CHANGED, {"project": project})

    def _is_project_open(self) -> bool:
        """Whether the project this command renamed is still the open one (the undo history outlives it)."""
        return self._project is not None and get_current_project(self.app_context) is self._project

    @override
    def undo(self) -> CommandResult:
        if not (self._applied and self.old_name is not None and self._project is not None):
            # The rename was never actually applied (execute() failed or was a
            # NOOP), so there's nothing to undo.
            return CommandResult.NOOP
        if not self._is_project_open():
            return CommandResult.ABORTED
        self._apply_rename(self._project, self.old_name)
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        if not (self._applied and self.old_name is not None and self._project is not None):
            # The rename was never actually applied (execute() failed or was a
            # NOOP), so there's nothing to redo.
            return CommandResult.NOOP
        if not self._is_project_open():
            return CommandResult.ABORTED
        self._apply_rename(self._project, self.new_name)
        return CommandResult.SUCCESS

    @override
    def cleanup(self) -> None:
        """No undo-only resource to release -- old_name and the renamed
        project are needed by both undo() and redo() (rename is symmetric via
        _apply_rename), and the project reference is small and goes away with
        the command."""
        return
