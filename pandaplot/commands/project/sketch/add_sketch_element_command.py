from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.sketch.sketch_change import emit_sketch_changed
from pandaplot.models.project.items.sketch import Sketch, SketchElement
from pandaplot.models.state import AppContext


class AddSketchElementCommand(Command):
    """Add a drawn element to a layer of a sketch.

    Redo re-inserts the same element object at the same index, so later
    commands that refer to its id keep working.
    """

    def __init__(self, app_context: AppContext, sketch: Sketch, layer_id: str, element: SketchElement, *, index: int | None = None):
        """
        Args:
            app_context: Application context (for the event bus).
            sketch: The sketch to draw on.
            layer_id: The layer that receives the element.
            element: The new element.
            index: Position within the layer; default is on top.
        """
        super().__init__()
        self.app_context = app_context
        self.sketch = sketch
        self.layer_id = layer_id
        self.element = element
        self.index = index
        self._inserted_index: int | None = None

    @override
    def execute(self) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if layer is None:
            self.logger.warning("Cannot add element: layer '%s' is not in sketch '%s'", self.layer_id, self.sketch.id)
            return CommandResult.FAILURE
        if layer.locked:
            self.logger.warning("Cannot add element: layer '%s' is locked", self.layer_id)
            return CommandResult.FAILURE
        try:
            inserted_index = self.sketch.add_element(self.layer_id, self.element, self.index)
        except ValueError:
            self.logger.warning("Cannot add element: id '%s' is already in sketch '%s'", self.element.id, self.sketch.id)
            return CommandResult.FAILURE
        self._inserted_index = inserted_index
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        if self._inserted_index is None:
            return CommandResult.FAILURE
        try:
            self.sketch.remove_element(self.element.id)
        except KeyError:
            self.logger.warning("Cannot undo add: element '%s' is no longer in sketch '%s'", self.element.id, self.sketch.id)
            return CommandResult.FAILURE
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        if self._inserted_index is None:
            return CommandResult.FAILURE
        try:
            self.sketch.add_element(self.layer_id, self.element, self._inserted_index)
        except (KeyError, ValueError):
            self.logger.warning("Cannot redo add of element '%s' to layer '%s'", self.element.id, self.layer_id)
            return CommandResult.FAILURE
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS
