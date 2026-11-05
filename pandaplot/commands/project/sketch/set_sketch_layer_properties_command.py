import math
from dataclasses import dataclass
from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.sketch.sketch_change import emit_sketch_changed
from pandaplot.models.project.items.sketch import Sketch, SketchLayer
from pandaplot.models.state import AppContext


@dataclass(frozen=True)
class LayerProperties:
    """A layer's display properties."""

    visible: bool
    locked: bool
    opacity: float

    @classmethod
    def of(cls, layer: SketchLayer) -> "LayerProperties":
        return cls(visible=layer.visible, locked=layer.locked, opacity=layer.opacity)


class SetSketchLayerPropertiesCommand(Command):
    """Show or hide, lock or unlock, or change the opacity of a layer in
    one undoable step. Properties left as None keep their value."""

    def __init__(
        self,
        app_context: AppContext,
        sketch: Sketch,
        layer_id: str,
        *,
        visible: bool | None = None,
        locked: bool | None = None,
        opacity: float | None = None,
    ):
        """
        Args:
            app_context: Application context (for the event bus).
            sketch: The sketch holding the layer.
            layer_id: Id of the layer to change.
            visible: Whether the layer is drawn.
            locked: Whether the layer's elements are protected from editing.
            opacity: The layer's opacity, from 0 to 1.
        """
        super().__init__()
        self.app_context = app_context
        self.sketch = sketch
        self.layer_id = layer_id
        self.visible = visible
        self.locked = locked
        self.opacity = opacity
        self._before: LayerProperties | None = None
        self._after: LayerProperties | None = None

    def _apply(self, properties: LayerProperties, action: str) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if layer is None:
            self.logger.warning("Cannot %s layer change: layer '%s' is not in sketch '%s'", action, self.layer_id, self.sketch.id)
            return CommandResult.FAILURE
        layer.visible = properties.visible
        layer.locked = properties.locked
        layer.opacity = properties.opacity
        self.sketch.update_modified_time()
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def execute(self) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if layer is None:
            self.logger.warning("Cannot change layer: layer '%s' is not in sketch '%s'", self.layer_id, self.sketch.id)
            return CommandResult.FAILURE
        if self.opacity is not None and not (math.isfinite(self.opacity) and 0.0 <= self.opacity <= 1.0):
            self.logger.warning("Cannot set layer opacity to %r: it must be between 0 and 1", self.opacity)
            return CommandResult.FAILURE
        before = LayerProperties.of(layer)
        after = LayerProperties(
            visible=before.visible if self.visible is None else self.visible,
            locked=before.locked if self.locked is None else self.locked,
            opacity=before.opacity if self.opacity is None else self.opacity,
        )
        if after == before:
            return CommandResult.NOOP
        result = self._apply(after, "execute")
        self._before, self._after = before, after
        return result

    @override
    def undo(self) -> CommandResult:
        if self._before is None:
            return CommandResult.FAILURE
        return self._apply(self._before, "undo")

    @override
    def redo(self) -> CommandResult:
        if self._after is None:
            return CommandResult.FAILURE
        return self._apply(self._after, "redo")
