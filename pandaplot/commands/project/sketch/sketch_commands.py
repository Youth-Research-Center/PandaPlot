from typing import Any, Dict, List, Tuple

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.models.project.items.sketch import Sketch, SketchElement


class AddSketchElementCommand(Command):
    """Command to add a SketchElement to a Sketch layer."""

    def __init__(self, sketch: Sketch, layer_id: str, element: SketchElement):
        super().__init__()
        self.sketch: Sketch = sketch
        self.layer_id: str = layer_id
        self.element: SketchElement = element

    def execute(self) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if not layer or layer.locked:
            return CommandResult.FAILURE
        layer.elements.append(self.element)
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if not layer:
            return CommandResult.FAILURE
        if self.element in layer.elements:
            layer.elements.remove(self.element)
            return CommandResult.SUCCESS
        return CommandResult.FAILURE

    def redo(self) -> CommandResult:
        return self.execute()


class DeleteSketchElementsCommand(Command):
    """Command to delete SketchElements from a Sketch layer, preserving original indices."""

    def __init__(self, sketch: Sketch, layer_id: str, element_ids: List[str]):
        super().__init__()
        self.sketch: Sketch = sketch
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
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        layer = self.sketch.get_layer(self.layer_id)
        if not layer:
            return CommandResult.FAILURE
        for idx, elem in sorted(self._removed, key=lambda x: x[0]):
            layer.elements.insert(idx, elem)
        return CommandResult.SUCCESS

    def redo(self) -> CommandResult:
        return self.execute()


class UpdateSketchElementStyleCommand(Command):
    """Command to update style properties of one or more SketchElements."""

    def __init__(self, sketch: Sketch, element_ids: List[str], property_dict: Dict[str, Any]):
        super().__init__()
        self.sketch: Sketch = sketch
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

        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id in self._old_properties:
                    old_vals = self._old_properties[elem.id]
                    for k, old_v in old_vals.items():
                        setattr(elem, k, old_v)
        return CommandResult.SUCCESS

    def redo(self) -> CommandResult:
        return self.execute()
