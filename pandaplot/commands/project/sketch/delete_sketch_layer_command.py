from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.sketch.sketch_change import emit_sketch_changed
from pandaplot.models.project.items.sketch import Sketch, SketchLayer
from pandaplot.models.state import AppContext


class DeleteSketchLayerCommand(Command):
    """Delete a layer together with its elements.

    The last remaining layer and locked layers can't be deleted. Undo puts
    the same layer object, elements included, back at its stacking index and
    re-activates the layer that was active before.
    """

    def __init__(self, app_context: AppContext, sketch: Sketch, layer_id: str):
        """
        Args:
            app_context: Application context (for the event bus).
            sketch: The sketch to delete the layer from.
            layer_id: Id of the layer to delete.
        """
        super().__init__()
        self.app_context = app_context
        self.sketch = sketch
        self.layer_id = layer_id
        self._removed: tuple[SketchLayer, int] | None = None
        self._previous_active_id: str | None = None

    def _refusal(self) -> str | None:
        """Why the layer can't be deleted now, or None."""
        layer = self.sketch.get_layer(self.layer_id)
        if layer is None:
            return f"layer '{self.layer_id}' is not in sketch '{self.sketch.id}'"
        if len(self.sketch.layers) == 1:
            return "a sketch must keep at least one layer"
        if layer.locked:
            return f"layer '{layer.name}' is locked"
        return None

    def _delete(self, action: str) -> CommandResult:
        refusal = self._refusal()
        if refusal is not None:
            self.logger.warning("Cannot %s layer delete: %s", action, refusal)
            return CommandResult.FAILURE
        previous_active_id = self.sketch.active_layer_id
        self._removed = self.sketch.remove_layer(self.layer_id)
        self._previous_active_id = previous_active_id
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def execute(self) -> CommandResult:
        return self._delete("execute")

    @override
    def undo(self) -> CommandResult:
        if self._removed is None:
            return CommandResult.FAILURE
        layer, index = self._removed
        if self.sketch.get_layer(layer.id) is not None:
            self.logger.warning("Cannot undo delete: layer '%s' is already back in sketch '%s'", layer.id, self.sketch.id)
            return CommandResult.FAILURE
        self.sketch.add_layer(layer, index)
        if self._previous_active_id is not None and self.sketch.get_layer(self._previous_active_id) is not None:
            self.sketch.active_layer_id = self._previous_active_id
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        if self._removed is None:
            return CommandResult.FAILURE
        return self._delete("redo")

    @override
    def cleanup(self) -> None:
        self._removed = None
