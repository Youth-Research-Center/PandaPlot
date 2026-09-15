from typing import Any, Dict, List, Tuple

from pandaplot.commands.base_command import Command, CommandResult
import math
from typing import Optional
from pandaplot.models.project.items.sketch import CircuitComponentElement, Sketch, SketchElement, WireElement


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


class MoveElementCommand(Command):
    """Command to move a SketchElement to a new position (x, y)."""

    def __init__(self, sketch: Sketch, element_id: str, new_x: float, new_y: float):
        super().__init__()
        self.sketch: Sketch = sketch
        self.element_id: str = element_id
        self.new_x: float = float(new_x)
        self.new_y: float = float(new_y)
        self._old_x: Optional[float] = None
        self._old_y: Optional[float] = None

    def execute(self) -> CommandResult:
        elem_found = None
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id == self.element_id:
                    elem_found = elem
                    break
        if not elem_found:
            return CommandResult.FAILURE

        self._old_x = elem_found.x
        self._old_y = elem_found.y

        if math.isclose(elem_found.x, self.new_x) and math.isclose(elem_found.y, self.new_y):
            return CommandResult.NOOP

        elem_found.x = self.new_x
        elem_found.y = self.new_y
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        elem_found = None
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id == self.element_id:
                    elem_found = elem
                    break
        if not elem_found or self._old_x is None or self._old_y is None:
            return CommandResult.FAILURE

        elem_found.x = self._old_x
        elem_found.y = self._old_y
        return CommandResult.SUCCESS

    def redo(self) -> CommandResult:
        return self.execute()


class UpdateWireWaypointsCommand(Command):
    """Command to update the waypoints of a WireElement."""

    def __init__(self, sketch: Sketch, wire_id: str, new_waypoints: List[Tuple[float, float]]):
        super().__init__()
        self.sketch: Sketch = sketch
        self.wire_id: str = wire_id
        self.new_waypoints: List[Tuple[float, float]] = [(float(p[0]), float(p[1])) for p in new_waypoints]
        self._old_waypoints: Optional[List[Tuple[float, float]]] = None

    def execute(self) -> CommandResult:
        wire = None
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id == self.wire_id and isinstance(elem, WireElement):
                    wire = elem
                    break
        if not wire:
            return CommandResult.FAILURE

        if self._old_waypoints is None:
            self._old_waypoints = list(wire.waypoints)

        if wire.waypoints == self.new_waypoints:
            return CommandResult.NOOP

        wire.waypoints = list(self.new_waypoints)
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        wire = None
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id == self.wire_id and isinstance(elem, WireElement):
                    wire = elem
                    break
        if not wire or self._old_waypoints is None:
            return CommandResult.FAILURE

        wire.waypoints = list(self._old_waypoints)
        return CommandResult.SUCCESS

    def redo(self) -> CommandResult:
        return self.execute()


class ConnectWireCommand(Command):
    """Command to connect or disconnect a WireElement endpoint (start_ref or end_ref)."""

    def __init__(self, sketch: Sketch, wire_id: str, end: str, ref: Optional[Tuple[str, str]]):
        super().__init__()
        self.sketch: Sketch = sketch
        self.wire_id: str = wire_id
        self.end: str = end
        self.ref: Optional[Tuple[str, str]] = ref
        self._old_ref: Optional[Tuple[str, str]] = None

    def execute(self) -> CommandResult:
        wire = None
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id == self.wire_id and isinstance(elem, WireElement):
                    wire = elem
                    break
        if not wire:
            return CommandResult.FAILURE

        attr = "start_ref" if self.end == "start" else "end_ref"
        self._old_ref = getattr(wire, attr)
        if self._old_ref == self.ref:
            return CommandResult.NOOP

        setattr(wire, attr, self.ref)
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        wire = None
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id == self.wire_id and isinstance(elem, WireElement):
                    wire = elem
                    break
        if not wire:
            return CommandResult.FAILURE

        attr = "start_ref" if self.end == "start" else "end_ref"
        setattr(wire, attr, self._old_ref)
        return CommandResult.SUCCESS

    def redo(self) -> CommandResult:
        return self.execute()


class TransformCircuitComponentCommand(Command):
    """Command to rotate and/or flip a CircuitComponentElement."""

    def __init__(
        self,
        sketch: Sketch,
        component_id: str,
        rotation: Optional[float] = None,
        flip_horizontal: Optional[bool] = None,
        flip_vertical: Optional[bool] = None,
    ):
        super().__init__()
        self.sketch: Sketch = sketch
        self.component_id: str = component_id
        self.rotation: Optional[float] = float(rotation) if rotation is not None else None
        self.flip_horizontal: Optional[bool] = flip_horizontal
        self.flip_vertical: Optional[bool] = flip_vertical

        self._old_rotation: Optional[float] = None
        self._old_flip_h: Optional[bool] = None
        self._old_flip_v: Optional[bool] = None

    def execute(self) -> CommandResult:
        comp = None
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id == self.component_id and isinstance(elem, CircuitComponentElement):
                    comp = elem
                    break
        if not comp:
            return CommandResult.FAILURE

        self._old_rotation = comp.rotation
        self._old_flip_h = comp.flip_horizontal
        self._old_flip_v = comp.flip_vertical

        new_rot = self.rotation if self.rotation is not None else comp.rotation
        new_fh = self.flip_horizontal if self.flip_horizontal is not None else comp.flip_horizontal
        new_fv = self.flip_vertical if self.flip_vertical is not None else comp.flip_vertical

        if (
            math.isclose(comp.rotation, new_rot)
            and comp.flip_horizontal == new_fh
            and comp.flip_vertical == new_fv
        ):
            return CommandResult.NOOP

        comp.rotation = new_rot
        comp.flip_horizontal = new_fh
        comp.flip_vertical = new_fv
        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        comp = None
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id == self.component_id and isinstance(elem, CircuitComponentElement):
                    comp = elem
                    break
        if not comp or self._old_rotation is None:
            return CommandResult.FAILURE

        comp.rotation = self._old_rotation
        comp.flip_horizontal = self._old_flip_h
        comp.flip_vertical = self._old_flip_v
        return CommandResult.SUCCESS

    def redo(self) -> CommandResult:
        return self.execute()


class UpdateComponentLabelCommand(Command):
    """Command to update designator and/or value label on CircuitComponentElements."""

    def __init__(
        self,
        sketch: Sketch,
        component_ids: List[str],
        designator: Optional[str] = None,
        value: Optional[str] = None,
    ):
        super().__init__()
        self.sketch: Sketch = sketch
        self.component_ids: List[str] = list(component_ids)
        self.designator: Optional[str] = designator
        self.value: Optional[str] = value
        self._old_labels: Dict[str, Tuple[str, str]] = {}

    def execute(self) -> CommandResult:
        if not self.component_ids or (self.designator is None and self.value is None):
            return CommandResult.NOOP

        comps: List[CircuitComponentElement] = []
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id in self.component_ids and isinstance(elem, CircuitComponentElement):
                    comps.append(elem)

        if not comps:
            return CommandResult.NOOP

        self._old_labels = {}
        has_change = False
        for c in comps:
            old_desig = c.designator
            old_val = c.value
            self._old_labels[c.id] = (old_desig, old_val)

            new_desig = self.designator if self.designator is not None else old_desig
            new_val = self.value if self.value is not None else old_val

            if new_desig != old_desig or new_val != old_val:
                has_change = True

        if not has_change:
            return CommandResult.NOOP

        for c in comps:
            if self.designator is not None:
                c.designator = self.designator
            if self.value is not None:
                c.value = self.value

        return CommandResult.SUCCESS

    def undo(self) -> CommandResult:
        for layer in self.sketch.layers:
            for elem in layer.elements:
                if elem.id in self._old_labels and isinstance(elem, CircuitComponentElement):
                    old_desig, old_val = self._old_labels[elem.id]
                    elem.designator = old_desig
                    elem.value = old_val
        return CommandResult.SUCCESS

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
