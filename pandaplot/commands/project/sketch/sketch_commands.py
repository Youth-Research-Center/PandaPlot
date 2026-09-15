from typing import Any, Dict, List, Optional, Tuple

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items.sketch import Sketch, SketchElement, SketchLayer
from pandaplot.models.state.app_context import AppContext


class SketchCommand(Command):
    """Base class for sketch mutation commands that emits content-changed events."""

    def __init__(self, sketch: Sketch, app_context: Optional[AppContext] = None):
        super().__init__()
        self.sketch: Sketch = sketch
        self.app_context: Optional[AppContext] = app_context

    def _notify_content_changed(self) -> None:
        if self.app_context and self.app_context.event_bus:
            self.app_context.event_bus.emit(
                ProjectEvents.PROJECT_ITEM_CONTENT_CHANGED,
                {"item_id": self.sketch.id, "sketch": self.sketch, "item": self.sketch},
            )


class AddSketchElementCommand(SketchCommand):
    """Command to add a SketchElement to a Sketch layer."""

    def __init__(
        self,
        sketch: Sketch,
        layer_id: str,
        element: SketchElement,
        app_context: Optional[AppContext] = None,
    ):
        super().__init__(sketch, app_context)
        self.layer_id: str = layer_id
        self.element: SketchElement = element

    def execute(self) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if not layer or layer.locked:
            return CommandResult.FAILURE
        layer.elements.append(self.element)
        self._notify_content_changed()
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if not layer:
            return CommandResult.FAILURE
        if self.element in layer.elements:
            layer.elements.remove(self.element)
            self._notify_content_changed()
            return CommandResult.SUCCESS
        return CommandResult.FAILURE

    def redo(self) -> CommandResult:
        return self.execute()


class DeleteSketchElementsCommand(SketchCommand):
    """Command to delete SketchElements from a Sketch layer, preserving original indices."""

    def __init__(
        self,
        sketch: Sketch,
        layer_id: str,
        element_ids: List[str],
        app_context: Optional[AppContext] = None,
    ):
        super().__init__(sketch, app_context)
        self.layer_id: str = layer_id
        self.element_ids: List[str] = list(element_ids)
        self._removed: List[Tuple[int, SketchElement]] = []

    def execute(self) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if not layer or layer.locked:
            return CommandResult.FAILURE
        self._removed = []
        target_ids = set(self.element_ids)
        remaining = []
        for idx, elem in enumerate(layer.elements):
            if elem.id in target_ids:
                self._removed.append((idx, elem))
            else:
                remaining.append(elem)

        if not self._removed:
            return CommandResult.NOOP

        layer.elements = remaining
        self._notify_content_changed()
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if not layer:
            return CommandResult.FAILURE
        for idx, elem in sorted(self._removed, key=lambda x: x[0]):
            layer.elements.insert(idx, elem)
        self._notify_content_changed()
        return CommandResult.SUCCESS

    def redo(self) -> CommandResult:
        return self.execute()


class MoveResizeSketchElementsCommand(SketchCommand):
    """Command to move or resize elements, storing before and after property states."""

    def __init__(
        self,
        sketch: Sketch,
        old_states: Dict[str, Dict[str, Any]],
        new_states: Dict[str, Dict[str, Any]],
        app_context: Optional[AppContext] = None,
    ):
        super().__init__(sketch, app_context)
        self.old_states: Dict[str, Dict[str, Any]] = old_states
        self.new_states: Dict[str, Dict[str, Any]] = new_states

    def _apply_states(self, states: Dict[str, Dict[str, Any]]) -> None:
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id in states:
                    elem_state = states[elem.id]
                    for k, v in elem_state.items():
                        if hasattr(elem, k):
                            setattr(elem, k, v)

    def execute(self) -> CommandResult:
        if not self.new_states or self.old_states == self.new_states:
            return CommandResult.NOOP
        self._apply_states(self.new_states)
        self._notify_content_changed()
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        if not self.old_states:
            return CommandResult.FAILURE
        self._apply_states(self.old_states)
        self._notify_content_changed()
        return CommandResult.SUCCESS

    def redo(self) -> CommandResult:
        return self.execute()


class UpdateSketchElementStyleCommand(SketchCommand):
    """Command to update style properties of one or more SketchElements."""

    def __init__(
        self,
        sketch: Sketch,
        element_ids: List[str],
        property_dict: Dict[str, Any],
        app_context: Optional[AppContext] = None,
    ):
        super().__init__(sketch, app_context)
        self.element_ids: List[str] = list(element_ids)
        self.property_dict: Dict[str, Any] = dict(property_dict)
        self._old_properties: Dict[str, Dict[str, Any]] = {}

    def execute(self) -> CommandResult:
        if not self.property_dict or not self.element_ids:
            return CommandResult.NOOP

        elements: List[SketchElement] = []
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id in self.element_ids:
                    elements.append(elem)

        if not elements:
            return CommandResult.NOOP

        self._old_properties = {}
        has_changes = False
        for elem in elements:
            old_vals = {}
            for k, new_v in self.property_dict.items():
                if hasattr(elem, k):
                    curr_v = getattr(elem, k)
                    old_vals[k] = curr_v
                    if curr_v != new_v:
                        has_changes = True
            self._old_properties[elem.id] = old_vals

        if not has_changes:
            return CommandResult.NOOP

        for elem in elements:
            for k, new_v in self.property_dict.items():
                if hasattr(elem, k):
                    setattr(elem, k, new_v)

        self._notify_content_changed()
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id in self._old_properties:
                    old_vals = self._old_properties[elem.id]
                    for k, old_v in old_vals.items():
                        setattr(elem, k, old_v)
        self._notify_content_changed()
        return CommandResult.SUCCESS

    def redo(self) -> CommandResult:
        return self.execute()


class LayerCommand(SketchCommand):
    """Base class for layer manipulation commands."""

    pass


class AddLayerCommand(LayerCommand):
    """Command to add a new layer to a sketch."""

    def __init__(
        self,
        sketch: Sketch,
        layer: SketchLayer,
        app_context: Optional[AppContext] = None,
    ):
        super().__init__(sketch, app_context)
        self.layer: SketchLayer = layer

    def execute(self) -> CommandResult:
        self.sketch.layers.append(self.layer)
        self.sketch.active_layer_id = self.layer.id
        self._notify_content_changed()
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        if self.layer in self.sketch.layers:
            self.sketch.layers.remove(self.layer)
            if self.sketch.active_layer_id == self.layer.id and self.sketch.layers:
                self.sketch.active_layer_id = self.sketch.layers[-1].id
            self._notify_content_changed()
            return CommandResult.SUCCESS
        return CommandResult.FAILURE

    def redo(self) -> CommandResult:
        return self.execute()


class DeleteLayerCommand(LayerCommand):
    """Command to delete a layer from a sketch."""

    def __init__(
        self,
        sketch: Sketch,
        layer_id: str,
        app_context: Optional[AppContext] = None,
    ):
        super().__init__(sketch, app_context)
        self.layer_id: str = layer_id
        self.deleted_layer: Optional[SketchLayer] = None
        self.deleted_index: int = -1

    def execute(self) -> CommandResult:
        if len(self.sketch.layers) <= 1:
            return CommandResult.NOOP

        layer = self.sketch.get_layer(self.layer_id)
        if not layer:
            return CommandResult.FAILURE

        self.deleted_index = self.sketch.layers.index(layer)
        self.deleted_layer = layer
        self.sketch.layers.remove(layer)

        if self.sketch.active_layer_id == self.layer_id and self.sketch.layers:
            self.sketch.active_layer_id = self.sketch.layers[-1].id

        self._notify_content_changed()
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        if self.deleted_layer and self.deleted_index >= 0:
            self.sketch.layers.insert(self.deleted_index, self.deleted_layer)
            self.sketch.active_layer_id = self.deleted_layer.id
            self._notify_content_changed()
            return CommandResult.SUCCESS
        return CommandResult.FAILURE

    def redo(self) -> CommandResult:
        return self.execute()


class ReorderLayersCommand(LayerCommand):
    """Command to reorder layers in a sketch."""

    def __init__(
        self,
        sketch: Sketch,
        new_layers: List[SketchLayer],
        app_context: Optional[AppContext] = None,
    ):
        super().__init__(sketch, app_context)
        self.new_layers: List[SketchLayer] = list(new_layers)
        self.old_layers: List[SketchLayer] = list(sketch.layers)

    def execute(self) -> CommandResult:
        if self.new_layers == self.old_layers:
            return CommandResult.NOOP
        self.sketch.layers = list(self.new_layers)
        self._notify_content_changed()
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        self.sketch.layers = list(self.old_layers)
        self._notify_content_changed()
        return CommandResult.SUCCESS

    def redo(self) -> CommandResult:
        return self.execute()


class UpdateLayerPropertiesCommand(LayerCommand):
    """Command to update visibility, lock, or opacity properties of a layer."""

    def __init__(
        self,
        sketch: Sketch,
        layer_id: str,
        property_dict: Dict[str, Any],
        app_context: Optional[AppContext] = None,
    ):
        super().__init__(sketch, app_context)
        self.layer_id: str = layer_id
        self.property_dict: Dict[str, Any] = dict(property_dict)
        self.old_properties: Dict[str, Any] = {}

    def execute(self) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if not layer or not self.property_dict:
            return CommandResult.NOOP

        has_changes = False
        self.old_properties = {}
        for k, new_v in self.property_dict.items():
            if hasattr(layer, k):
                curr_v = getattr(layer, k)
                self.old_properties[k] = curr_v
                if curr_v != new_v:
                    has_changes = True

        if not has_changes:
            return CommandResult.NOOP

        for k, new_v in self.property_dict.items():
            if hasattr(layer, k):
                setattr(layer, k, new_v)

        self._notify_content_changed()
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if not layer:
            return CommandResult.FAILURE
        for k, old_v in self.old_properties.items():
            setattr(layer, k, old_v)
        self._notify_content_changed()
        return CommandResult.SUCCESS

    def redo(self) -> CommandResult:
        return self.execute()
