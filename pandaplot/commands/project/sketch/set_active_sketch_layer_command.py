from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.sketch.sketch_change import emit_sketch_changed
from pandaplot.models.project.items.sketch import Sketch
from pandaplot.models.state import AppContext


class SetActiveSketchLayerCommand(Command):
    """Choose the layer new elements are drawn on.

    The active layer is saved with the sketch, so this marks the project as
    modified, but picking a layer is not an edit the user would undo, so it
    takes no undo slot.
    """

    def __init__(self, app_context: AppContext, sketch: Sketch, layer_id: str):
        """
        Args:
            app_context: Application context (for the event bus).
            sketch: The sketch holding the layer.
            layer_id: Id of the layer to make active.
        """
        super().__init__()
        self.app_context = app_context
        self.sketch = sketch
        self.layer_id = layer_id

    @override
    def execute(self) -> CommandResult:
        if self.sketch.get_layer(self.layer_id) is None:
            self.logger.warning("Cannot activate layer: layer '%s' is not in sketch '%s'", self.layer_id, self.sketch.id)
            return CommandResult.FAILURE
        if self.sketch.active_layer_id == self.layer_id:
            return CommandResult.NOOP
        self.sketch.active_layer_id = self.layer_id
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        """Never called: the command takes no undo slot."""
        return CommandResult.NOOP

    @override
    def redo(self) -> CommandResult:
        """Never called: the command takes no undo slot."""
        return CommandResult.NOOP

    @override
    def occupies_undo_slot(self) -> bool:
        return False
