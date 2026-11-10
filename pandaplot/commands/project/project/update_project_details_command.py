"""Command for editing a project's details: name, notes, cover image and example settings."""

from dataclasses import dataclass
from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.example_info import ExampleInfo
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext


@dataclass(frozen=True)
class _ProjectDetails:
    """The four project values the command edits."""

    name: str
    description: str
    cover_image: bytes | None
    example_info: ExampleInfo

    @classmethod
    def of(cls, project: Project) -> "_ProjectDetails":
        return cls(project.name, project.description, project.cover_image, project.example_info)


class UpdateProjectDetailsCommand(Command):
    """Set the current project's name, notes (``description``), cover image and example settings.

    Returns NOOP when none of the four values changes. ``undo()``/``redo()`` act on the project the command
    edited and return ABORTED, changing nothing, when another project is open. A name change emits the same
    ``PROJECT_CHANGED`` event as ``RenameProjectCommand``, which is what the window title and the project
    tree listen to; the other fields use the same event.
    """

    def __init__(
        self,
        app_context: AppContext,
        *,
        name: str,
        description: str,
        cover_image: bytes | None,
        example_info: ExampleInfo,
    ):
        super().__init__()
        self.app_context = app_context
        self.ui_controller = app_context.get_ui_controller()
        self._new = _ProjectDetails(name.strip(), description, cover_image, example_info)
        self._old: _ProjectDetails | None = None
        self._project: Project | None = None
        self._applied = False

    @override
    def execute(self) -> CommandResult:
        project = get_current_project(self.app_context)
        if project is None:
            self.logger.warning("UpdateProjectDetailsCommand.execute: no project is loaded")
            self.ui_controller.show_warning_message("Project Details", "Please open or create a project first.")
            return CommandResult.FAILURE
        if not self._new.name:
            self.logger.warning("UpdateProjectDetailsCommand.execute: rejected empty name for project '%s'", project.name)
            self.ui_controller.show_error_message("Project Details", "Project name cannot be empty.")
            return CommandResult.FAILURE

        snapshot = _ProjectDetails.of(project)
        if snapshot == self._new:
            return CommandResult.NOOP

        self._apply(project, self._new)
        # Remember the project and its previous state only now that the change has been applied.
        self._project = project
        self._old = snapshot
        self._applied = True
        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        return self._replay(self._old)

    @override
    def redo(self) -> CommandResult:
        return self._replay(self._new)

    def _replay(self, details: _ProjectDetails | None) -> CommandResult:
        if not self._applied or details is None or self._project is None:
            return CommandResult.NOOP
        # The undo history outlives the project: after Open or New the command's project is no longer the open one.
        if get_current_project(self.app_context) is not self._project:
            self.logger.warning("UpdateProjectDetailsCommand: the edited project is no longer the open project; nothing changed")
            return CommandResult.ABORTED
        self._apply(self._project, details)
        return CommandResult.SUCCESS

    def _apply(self, project: Project, details: _ProjectDetails) -> None:
        """Assign all four values and announce the change."""
        project.name = details.name
        project.description = details.description
        project.cover_image = details.cover_image
        project.example_info = details.example_info
        self.app_context.event_bus.emit(ProjectEvents.PROJECT_CHANGED, {"project": project})

    @override
    def cleanup(self) -> None:
        """Drop the cover image bytes and the project reference the command holds."""
        self._old = None
        self._project = None
        self._new = _ProjectDetails(self._new.name, self._new.description, None, self._new.example_info)
