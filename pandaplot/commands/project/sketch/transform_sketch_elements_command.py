import dataclasses
from typing import Any, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.sketch.sketch_change import emit_sketch_changed, locked_element_ids
from pandaplot.models.project.items.sketch import Sketch, SketchElement
from pandaplot.models.state import AppContext

type GeometryChanges = dict[str, dict[str, Any]]


def _copy_value(value: Any) -> Any:
    # Freehand points are the only list-valued geometry; copy it so a
    # stored before/after state can't change under the command.
    return list(value) if isinstance(value, list) else value


class TransformSketchElementsCommand(Command):
    """Move, resize or rotate elements by setting their geometry fields.

    One command covers a whole interaction (e.g. dragging a multi-element
    selection), so it undoes as one step.
    """

    def __init__(self, app_context: AppContext, sketch: Sketch, changes: GeometryChanges):
        """
        Args:
            app_context: Application context (for the event bus).
            sketch: The sketch holding the elements.
            changes: Element id -> {geometry field: new value}. Fields must
                be in the element type's `GEOMETRY_FIELDS`.
        """
        super().__init__()
        self.app_context = app_context
        self.sketch = sketch
        self.changes = {element_id: {name: _copy_value(value) for name, value in fields.items()} for element_id, fields in changes.items()}
        self._before: GeometryChanges = {}

    def _elements(self) -> dict[str, SketchElement] | None:
        """Every changed element by id, or None if any is missing."""
        elements = {}
        for element_id in self.changes:
            found = self.sketch.find_element(element_id)
            if found is None:
                return None
            elements[element_id] = found[1]
        return elements

    def _validate(self, elements: dict[str, SketchElement]) -> str | None:
        """Why `changes` can't be applied, or None if it can."""
        for element_id, fields in self.changes.items():
            element = elements[element_id]
            unknown = set(fields) - type(element).GEOMETRY_FIELDS
            if unknown:
                return f"{sorted(unknown)} are not geometry fields of a {element.TYPE} element"
            try:
                # Construct, without keeping, the changed element so its
                # invariants (e.g. non-negative size) are checked first.
                dataclasses.replace(element, **fields)
            except (TypeError, ValueError) as error:
                return f"invalid geometry for element '{element_id}': {error}"
        return None

    def _apply(self, elements: dict[str, SketchElement], state: GeometryChanges) -> None:
        for element_id, fields in state.items():
            for name, value in fields.items():
                setattr(elements[element_id], name, _copy_value(value))
        self.sketch.update_modified_time()
        emit_sketch_changed(self.app_context, self.sketch)

    @override
    def execute(self) -> CommandResult:
        elements = self._elements()
        if elements is None:
            self.logger.warning("Cannot transform: not every element of %s is in sketch '%s'", list(self.changes), self.sketch.id)
            return CommandResult.FAILURE
        locked = locked_element_ids(self.sketch, list(self.changes))
        if locked:
            self.logger.warning("Cannot transform elements on locked layers: %s", locked)
            return CommandResult.FAILURE
        problem = self._validate(elements)
        if problem is not None:
            self.logger.warning("Cannot transform: %s", problem)
            return CommandResult.FAILURE
        before = {
            element_id: {name: _copy_value(getattr(elements[element_id], name)) for name in fields}
            for element_id, fields in self.changes.items()
        }
        if before == self.changes:
            return CommandResult.NOOP
        self._apply(elements, self.changes)
        self._before = before
        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        return self._restore(self._before, "undo")

    @override
    def redo(self) -> CommandResult:
        return self._restore(self.changes, "redo")

    def _restore(self, state: GeometryChanges, operation: str) -> CommandResult:
        if not self._before:
            return CommandResult.FAILURE
        elements = self._elements()
        if elements is None:
            self.logger.warning("Cannot %s transform: not every element of %s is in sketch '%s'", operation, list(self.changes), self.sketch.id)
            return CommandResult.FAILURE
        self._apply(elements, state)
        return CommandResult.SUCCESS
