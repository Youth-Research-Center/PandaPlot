from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.sketch.sketch_change import emit_sketch_changed
from pandaplot.models.project.items.sketch import Sketch
from pandaplot.models.state import AppContext


class ReorderSketchLayerCommand(Command):
    """Move a layer to another stacking index (0 is the bottom)."""

    def __init__(self, app_context: AppContext, sketch: Sketch, layer_id: str, new_index: int):
        """
        Args:
            app_context: Application context (for the event bus).
            sketch: The sketch holding the layer.
            layer_id: Id of the layer to move.
            new_index: Its new stacking index, clamped to the valid range.
        """
        super().__init__()
        self.app_context = app_context
        self.sketch = sketch
        self.layer_id = layer_id
        self.new_index = new_index
        self._old_index: int | None = None

    def _move_to(self, index: int, action: str) -> CommandResult:
        if self.sketch.get_layer(self.layer_id) is None:
            self.logger.warning("Cannot %s layer move: layer '%s' is not in sketch '%s'", action, self.layer_id, self.sketch.id)
            return CommandResult.FAILURE
        self.sketch.move_layer(self.layer_id, index)
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def execute(self) -> CommandResult:
        old_index = self.sketch.layer_index(self.layer_id)
        if old_index is None:
            self.logger.warning("Cannot move layer: layer '%s' is not in sketch '%s'", self.layer_id, self.sketch.id)
            return CommandResult.FAILURE
        self.new_index = min(max(self.new_index, 0), len(self.sketch.layers) - 1)
        if self.new_index == old_index:
            return CommandResult.NOOP
        self._old_index = old_index
        return self._move_to(self.new_index, "execute")

    @override
    def undo(self) -> CommandResult:
        if self._old_index is None:
            return CommandResult.FAILURE
        return self._move_to(self._old_index, "undo")

    @override
    def redo(self) -> CommandResult:
        if self._old_index is None:
            return CommandResult.FAILURE
        return self._move_to(self.new_index, "redo")
