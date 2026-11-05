from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.sketch.sketch_change import emit_sketch_changed
from pandaplot.models.project.items.sketch import Sketch, SketchLayer
from pandaplot.models.state import AppContext


def next_layer_name(sketch: Sketch) -> str:
    """'Layer N' with the smallest N above the layer count not already used."""
    names = {layer.name for layer in sketch.layers}
    number = len(sketch.layers) + 1
    while f"Layer {number}" in names:
        number += 1
    return f"Layer {number}"


class AddSketchLayerCommand(Command):
    """Add an empty layer and make it the active one.

    By default the layer goes directly above the active layer and is named
    'Layer N'. Undo removes it and re-activates the previously active layer.
    """

    def __init__(self, app_context: AppContext, sketch: Sketch, *, name: str | None = None, index: int | None = None):
        """
        Args:
            app_context: Application context (for the event bus).
            sketch: The sketch to add the layer to.
            name: Name of the new layer; default 'Layer N'.
            index: Stacking index for the new layer; default above the active layer.
        """
        super().__init__()
        self.app_context = app_context
        self.sketch = sketch
        self._name = name
        self._index = index
        self.layer: SketchLayer | None = None
        self._added_index: int | None = None
        self._previous_active_id: str | None = None

    @override
    def execute(self) -> CommandResult:
        name = self._name.strip() if self._name is not None else ""
        layer = SketchLayer(name=name or next_layer_name(self.sketch))
        index = self._index
        if index is None:
            active_index = self.sketch.layer_index(self.sketch.active_layer_id)
            index = len(self.sketch.layers) if active_index is None else active_index + 1
        previous_active_id = self.sketch.active_layer_id
        self._added_index = self.sketch.add_layer(layer, index)
        self.sketch.active_layer_id = layer.id
        self.layer = layer
        self._previous_active_id = previous_active_id
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        if self.layer is None:
            return CommandResult.FAILURE
        if self.sketch.get_layer(self.layer.id) is None:
            self.logger.warning("Cannot undo add: layer '%s' is not in sketch '%s'", self.layer.id, self.sketch.id)
            return CommandResult.FAILURE
        self.sketch.remove_layer(self.layer.id)
        if self._previous_active_id is not None and self.sketch.get_layer(self._previous_active_id) is not None:
            self.sketch.active_layer_id = self._previous_active_id
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        if self.layer is None or self._added_index is None:
            return CommandResult.FAILURE
        if self.sketch.get_layer(self.layer.id) is not None:
            self.logger.warning("Cannot redo add: layer '%s' is already in sketch '%s'", self.layer.id, self.sketch.id)
            return CommandResult.FAILURE
        self._previous_active_id = self.sketch.active_layer_id
        self.sketch.add_layer(self.layer, self._added_index)
        self.sketch.active_layer_id = self.layer.id
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS
