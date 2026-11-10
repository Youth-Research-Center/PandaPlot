"""Loads bundled example projects for the examples browser's chart previews."""

import logging

from pandaplot.models.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.data_managers.project_manager import ProjectManager
from pandaplot.utils.examples import ExampleProject


class ExampleProjectLoader:
    """Loads each example's full project once and keeps it for the loader's lifetime.

    Loading goes through the application's `ProjectManager`, like opening a project does, but the result is only
    returned: application state, the event bus and recent-project lists are never touched, and the file is only read.
    A project that fails to load is remembered as failed so it is not read again.
    """

    def __init__(self, app_context: AppContext) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self._project_manager = app_context.get_manager(ProjectManager)
        self._projects: dict[str, Project | None] = {}

    def load(self, example: ExampleProject) -> Project | None:
        """Return the example's project, or None if it cannot be loaded (logged)."""
        if example.path not in self._projects:
            try:
                self._projects[example.path] = self._project_manager.load_project(example.path)
            except Exception:
                self.logger.exception("Could not load example project '%s' for previews", example.path)
                self._projects[example.path] = None
        return self._projects[example.path]
