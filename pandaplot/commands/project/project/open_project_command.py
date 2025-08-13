import logging
from typing import Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.commands.project.project.load_project_command import LoadProjectCommand
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.data_managers.project_manager import ProjectManager


class OpenProjectCommand(Command):
    """
    Command to open a project file through a file dialog.
    This command follows the MVC pattern by:
    1. Using UIController to show file dialog (UI interaction)
    2. Delegating to LoadProjectCommand for actual loading (business logic)
    3. Handling user cancellation gracefully
    """

    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context
        self.project_manager = ProjectManager()
        self.load_command: Optional[LoadProjectCommand] = None
        self.was_executed = False

    @override
    def execute(self):
        """Execute the open project command."""
        try:
            self.logger.info("Executing OpenProjectCommand")
            # Show file dialog to user
            file_path = self.app_context.ui_controller.show_open_project_dialog()

            if file_path is None:
                # User cancelled the dialog
                self.logger.info("Open project cancelled by user")
                self.was_executed = False
                return

            self.logger.info(f"Opening project: {file_path}")

            # Validate the file before attempting to load
            if not self.project_manager.validate_project_file(file_path):
                self.app_context.ui_controller.show_error_message(
                    "Invalid Project File",
                    f"The selected file is not a valid project file:\n{file_path}"
                )
                self.was_executed = False
                return

            # Check if we need to save current project
            if self.app_context.app_state.has_project:
                should_continue = self.app_context.ui_controller.show_question(
                    "Open Project",
                    "Opening a new project will close the current project.\n"
                    "Any unsaved changes will be lost.\n\n"
                    "Do you want to continue?"
                )

                if not should_continue:
                    self.logger.info(
                        "Open project cancelled by user (current project protection)")
                    self.was_executed = False
                    return

            # Create and execute load command
            self.load_command = LoadProjectCommand(
                self.app_context, file_path)
            self.load_command.execute()

            self.was_executed = True
            self.logger.info(f"Project opened successfully: {file_path}")

            # Show success message
            project = self.app_context.app_state.current_project
            if project:
                self.app_context.ui_controller.show_info_message(
                    "Project Opened",
                    f"Successfully opened project: {project.name}"
                )

        except Exception as e:
            error_msg = f"Failed to open project: {str(e)}"
            self.logger.error(error_msg)
            self.app_context.ui_controller.show_error_message(
                "Open Project Error", error_msg)
            self.was_executed = False

    def undo(self):
        """Undo the open project command."""
        if self.was_executed and self.load_command:
            self.load_command.undo()
            self.logger.info("Open project command undone")
        else:
            self.logger.debug("Nothing to undo for open project command")

    def redo(self):
        """Redo the open project command."""
        if self.was_executed and self.load_command:
            self.load_command.redo()
            self.logger.info("Open project command redone")
        else:
            # Re-execute the command (will show dialog again)
            self.logger.debug("Re-executing open project command")
            self.execute()
