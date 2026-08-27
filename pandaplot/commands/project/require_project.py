"""Shared "no project yet" recovery helper for commands that require a
project to act on -- e.g. importing data or creating a chart. Offers to
create one on the spot instead of leaving the user at a dead end.
"""
from pandaplot.commands.project.project.new_project_command import NewProjectCommand
from pandaplot.models.state import AppContext


def ensure_project_or_offer_create(app_context: AppContext, title: str, message: str) -> bool:
    """True once a project is open -- either it already was, or the user
    chose "Create Project" and one was created just now. False if the user
    cancelled.
    """
    app_state = app_context.get_app_state()
    if app_state.has_project and app_state.current_project:
        return True

    ui_controller = app_context.get_ui_controller()
    if not ui_controller.show_action_or_cancel(title, message, "Create Project"):
        return False

    app_context.get_command_executor().execute_command(NewProjectCommand(app_context))
    return bool(app_state.has_project and app_state.current_project)
