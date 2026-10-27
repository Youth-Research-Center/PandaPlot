import dataclasses
from collections.abc import Iterable
from typing import Any, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.sketch.sketch_change import emit_sketch_changed, locked_element_ids
from pandaplot.models.project.items.sketch import Sketch, SketchElement
from pandaplot.models.project.items.sketch.sketch_element import STYLE_VALUE_CHECKS
from pandaplot.models.state import AppContext

type StyleState = dict[str, dict[str, Any]]


class UpdateSketchElementStyleCommand(Command):
    """Set style fields (colours, stroke, font) on several elements in one
    undoable step.

    Each field is applied to the elements whose type draws with it (its
    `STYLE_FIELDS`), so setting a fill on a selection of a rectangle and a
    line fills the rectangle and leaves the line alone.
    """

    def __init__(self, app_context: AppContext, sketch: Sketch, element_ids: Iterable[str], style: dict[str, Any]):
        """
        Args:
            app_context: Application context (for the event bus).
            sketch: The sketch holding the elements.
            element_ids: Ids of the elements to restyle.
            style: Style field -> new value, e.g. `{"stroke_color": "#FF0000"}`.
        """
        super().__init__()
        self.app_context = app_context
        self.sketch = sketch
        self.element_ids = list(dict.fromkeys(element_ids))
        self.style = dict(style)
        self._changes: StyleState = {}
        self._before: StyleState = {}

    def _elements(self) -> dict[str, SketchElement] | None:
        """Every element by id, or None if any is missing."""
        elements = {}
        for element_id in self.element_ids:
            found = self.sketch.find_element(element_id)
            if found is None:
                return None
            elements[element_id] = found[1]
        return elements

    def _plan(self, elements: dict[str, SketchElement]) -> StyleState | str:
        """The changes per element, or why the style can't be applied."""
        for name, value in self.style.items():
            check = STYLE_VALUE_CHECKS.get(name)
            if check is None:
                return f"{name!r} is not a style field"
            if not check(value):
                return f"invalid value {value!r} for {name!r}"
            if not any(name in type(element).STYLE_FIELDS for element in elements.values()):
                return f"none of the elements has {name!r}"
        changes = {}
        for element_id, element in elements.items():
            fields = {name: value for name, value in self.style.items() if name in type(element).STYLE_FIELDS}
            if not fields:
                continue
            try:
                # Construct, without keeping, the restyled element so its own
                # invariants are checked before anything changes.
                dataclasses.replace(element, **fields)
            except (TypeError, ValueError) as error:
                return f"invalid style for element '{element_id}': {error}"
            changes[element_id] = fields
        return changes

    def _apply(self, elements: dict[str, SketchElement], state: StyleState) -> None:
        for element_id, fields in state.items():
            for name, value in fields.items():
                setattr(elements[element_id], name, value)
        self.sketch.update_modified_time()
        emit_sketch_changed(self.app_context, self.sketch)

    @override
    def execute(self) -> CommandResult:
        if not self.element_ids or not self.style:
            return CommandResult.NOOP
        elements = self._elements()
        if elements is None:
            self.logger.warning("Cannot restyle: not every element of %s is in sketch '%s'", self.element_ids, self.sketch.id)
            return CommandResult.FAILURE
        locked = locked_element_ids(self.sketch, self.element_ids)
        if locked:
            self.logger.warning("Cannot restyle elements on locked layers: %s", locked)
            return CommandResult.FAILURE
        plan = self._plan(elements)
        if isinstance(plan, str):
            self.logger.warning("Cannot restyle: %s", plan)
            return CommandResult.FAILURE
        before = {element_id: {name: getattr(elements[element_id], name) for name in fields} for element_id, fields in plan.items()}
        if before == plan:
            return CommandResult.NOOP
        self._apply(elements, plan)
        self._changes, self._before = plan, before
        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        return self._restore(self._before, "undo")

    @override
    def redo(self) -> CommandResult:
        return self._restore(self._changes, "redo")

    def _restore(self, state: StyleState, operation: str) -> CommandResult:
        if not self._changes:
            return CommandResult.FAILURE
        elements = self._elements()
        if elements is None:
            self.logger.warning("Cannot %s restyle: not every element of %s is in sketch '%s'", operation, self.element_ids, self.sketch.id)
            return CommandResult.FAILURE
        self._apply(elements, state)
        return CommandResult.SUCCESS
