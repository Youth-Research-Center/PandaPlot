from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.sketch.sketch_change import emit_sketch_changed
from pandaplot.models.project.items.sketch import Sketch
from pandaplot.models.state import AppContext


class RenameSketchLayerCommand(Command):
    """Rename a layer. Surrounding whitespace is dropped and an empty name
    is refused; names don't have to be unique."""

    def __init__(self, app_context: AppContext, sketch: Sketch, layer_id: str, new_name: str):
        """
        Args:
            app_context: Application context (for the event bus).
            sketch: The sketch holding the layer.
            layer_id: Id of the layer to rename.
            new_name: The new name.
        """
        super().__init__()
        self.app_context = app_context
        self.sketch = sketch
        self.layer_id = layer_id
        self.new_name = new_name.strip()
        self._old_name: str | None = None

    def _set_name(self, name: str, action: str) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if layer is None:
            self.logger.warning("Cannot %s layer rename: layer '%s' is not in sketch '%s'", action, self.layer_id, self.sketch.id)
            return CommandResult.FAILURE
        layer.name = name
        self.sketch.update_modified_time()
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def execute(self) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if layer is None:
            self.logger.warning("Cannot rename layer: layer '%s' is not in sketch '%s'", self.layer_id, self.sketch.id)
            return CommandResult.FAILURE
        if not self.new_name:
            self.logger.warning("Cannot rename layer '%s' to an empty name", self.layer_id)
            return CommandResult.FAILURE
        if self.new_name == layer.name:
            return CommandResult.NOOP
        old_name = layer.name
        result = self._set_name(self.new_name, "execute")
        self._old_name = old_name
        return result

    @override
    def undo(self) -> CommandResult:
        if self._old_name is None:
            return CommandResult.FAILURE
        return self._set_name(self._old_name, "undo")

    @override
    def redo(self) -> CommandResult:
        if self._old_name is None:
            return CommandResult.FAILURE
        return self._set_name(self.new_name, "redo")
