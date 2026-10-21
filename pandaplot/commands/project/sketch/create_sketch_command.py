from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.commands.project.require_project import ensure_project_or_offer_create
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import ItemCollection, Sketch
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext

SKETCH_ITEM_TYPE = "sketch"


class CreateSketchCommand(Command):
    """Create an empty sketch (one default layer) in the project.

    Undo and redo act on the project the sketch was created in, and redo
    re-adds the same Sketch object at the position it held.
    """

    def __init__(self, app_context: AppContext, *, sketch_name: str | None = None, folder_id: str | None = None):
        """
        Args:
            app_context: Application context.
            sketch_name: Name for the sketch; default "New Sketch N".
            folder_id: Folder to create it in; default the project root.
        """
        super().__init__()
        self.app_context = app_context
        self.sketch_name = sketch_name
        self.folder_id = folder_id
        self.sketch: Sketch | None = None
        self.project: Project | None = None
        self._index: int | None = None

    def _default_name(self, project: Project) -> str:
        count = sum(isinstance(item, Sketch) for item in project.get_all_items())
        return f"New Sketch {count + 1}"

    def _emit(self, event: str, project: Project, sketch: Sketch) -> None:
        self.app_context.event_bus.emit(event, {
            "project": project,
            "item_id": sketch.id,
            "item_type": SKETCH_ITEM_TYPE,
            "item_name": sketch.name,
            "item": sketch,
            "parent_id": self.folder_id,
        })

    @override
    def execute(self) -> CommandResult:
        if get_current_project(self.app_context) is None and not ensure_project_or_offer_create(
            self.app_context, "New Sketch", "Creating a sketch requires a project. Create a new project to continue?",
        ):
            return CommandResult.FAILURE
        project = get_current_project(self.app_context)
        if project is None:
            self.logger.warning("Cannot create sketch: no project is loaded")
            return CommandResult.FAILURE

        name = self.sketch_name.strip() if self.sketch_name is not None else self._default_name(project)
        if not name:
            self.logger.warning("Cannot create sketch: the name is empty")
            return CommandResult.FAILURE

        sketch = Sketch(name=name)
        try:
            project.add_item(sketch, parent_id=self.folder_id)
        except ValueError:
            self.logger.exception("Cannot create sketch '%s'", name)
            return CommandResult.FAILURE
        self.sketch = sketch
        self.project = project
        self._emit(ProjectEvents.PROJECT_ITEM_ADDED, project, sketch)
        self.logger.info("Created sketch '%s' (id=%s) in %s", name, sketch.id, self.folder_id or "root")
        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        if self.project is None or self.sketch is None:
            return CommandResult.FAILURE
        if self.project.find_item(self.sketch.id) is not self.sketch:
            self.logger.warning("Cannot undo: sketch '%s' is no longer in the project", self.sketch.id)
            return CommandResult.FAILURE
        parent = self.project.find_item(self.sketch.parent_id) if self.sketch.parent_id is not None else None
        container = parent if isinstance(parent, ItemCollection) else self.project.root
        siblings = list(container.items)
        self._index = siblings.index(self.sketch.id) if self.sketch.id in siblings else None
        self.project.remove_item(self.sketch)
        self._emit(ProjectEvents.PROJECT_ITEM_REMOVED, self.project, self.sketch)
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        if self.project is None or self.sketch is None:
            return CommandResult.FAILURE
        try:
            self.project.add_item(self.sketch, parent_id=self.folder_id, index=self._index)
        except ValueError:
            self.logger.exception("Cannot redo creation of sketch '%s'", self.sketch.id)
            return CommandResult.FAILURE
        self._emit(ProjectEvents.PROJECT_ITEM_ADDED, self.project, self.sketch)
        return CommandResult.SUCCESS

    @override
    def cleanup(self) -> None:
        self.project = None
        self.sketch = None
