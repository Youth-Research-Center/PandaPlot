import uuid
from typing import Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.commands.project.require_project import ensure_project_or_offer_create
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items.sketch import Sketch
from pandaplot.models.state import AppContext, AppState


class CreateSketchCommand(Command):
    """Command to create a new sketch in the project."""

    def __init__(self, app_context: AppContext, sketch_name: Optional[str] = None,
                 folder_id: Optional[str] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.sketch_name = sketch_name
        self.folder_id = folder_id

        self.created_sketch_id = None
        self.created_sketch = None
        self.project = None

    @override
    def execute(self) -> CommandResult:
        try:
            if get_current_project(self.app_context) is None:
                if not ensure_project_or_offer_create(
                    self.app_context, "New Sketch",
                    "Creating a sketch requires a project. Create a new project to continue?",
                ):
                    return CommandResult.FAILURE

            self.project = get_current_project(self.app_context)
            if not self.project:
                return CommandResult.FAILURE

            name = self.sketch_name or "New Sketch"
            self.created_sketch_id = str(uuid.uuid4())
            self.created_sketch = Sketch(
                id=self.created_sketch_id,
                name=name
            )

            self.project.add_item(self.created_sketch, parent_id=self.folder_id)

            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                "project": self.project,
                "sketch_id": self.created_sketch_id,
                "sketch_name": name,
                "folder_id": self.folder_id,
                "sketch": self.created_sketch
            })

            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to create sketch: {str(e)}"
            self.logger.error("CreateSketchCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Create Sketch Error", error_msg)
            return CommandResult.FAILURE

    def undo(self) -> CommandResult:
        try:
            if self.created_sketch_id and self.app_state.has_project:
                project = get_current_project(self.app_context)
                if not project:
                    return CommandResult.FAILURE

                sketch = project.find_item(self.created_sketch_id)
                if sketch is None:
                    return CommandResult.FAILURE

                project.remove_item(sketch)

                self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                    "project": project,
                    "sketch_id": self.created_sketch_id,
                    "sketch": self.created_sketch
                })
                return CommandResult.SUCCESS
            else:
                return CommandResult.NOOP

        except Exception as e:
            error_msg = f"Failed to undo create sketch: {str(e)}"
            self.logger.error("CreateSketchCommand Undo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)
            return CommandResult.FAILURE

    def redo(self) -> CommandResult:
        try:
            if self.created_sketch_id and self.created_sketch is not None and self.app_state.has_project:
                project = get_current_project(self.app_context)
                if not project:
                    return CommandResult.FAILURE

                project.add_item(self.created_sketch, parent_id=self.folder_id)

                self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                    "project": project,
                    "sketch_id": self.created_sketch_id,
                    "sketch_name": self.created_sketch.name,
                    "folder_id": self.folder_id,
                    "sketch": self.created_sketch
                })
                return CommandResult.SUCCESS
            else:
                return CommandResult.FAILURE

        except Exception as e:
            error_msg = f"Failed to redo create sketch: {str(e)}"
            self.logger.error("CreateSketchCommand Redo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        self.project = None
