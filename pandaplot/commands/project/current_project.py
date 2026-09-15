"""Shared "is a project open" check for commands that look something up in
the current project (as opposed to require_project.ensure_project_or_offer_create,
which interactively offers to create one)."""

from typing import Optional

from pandaplot.models.project import Project
from pandaplot.models.state import AppContext


def get_current_project(app_context: AppContext) -> Optional[Project]:
    """The current project, or None if none is open. Also guards against
    has_project being True while current_project is somehow None -- an
    inconsistent state that should never happen but is handled the same as
    "no project" rather than raising."""
    app_state = app_context.get_app_state()
    if not app_state.has_project or not app_state.current_project:
        return None
    return app_state.current_project
