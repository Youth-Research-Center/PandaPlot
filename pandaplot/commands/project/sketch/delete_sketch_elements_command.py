from collections.abc import Iterable
from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.sketch.sketch_change import emit_sketch_changed, locked_element_ids
from pandaplot.models.project.items.sketch import Sketch, SketchElement
from pandaplot.models.state import AppContext


class DeleteSketchElementsCommand(Command):
    """Delete elements, possibly from several layers, in one undoable step.

    Undo puts every element back on its layer at its original index, so the
    layer's drawing order is unchanged.
    """

    def __init__(self, app_context: AppContext, sketch: Sketch, element_ids: Iterable[str]):
        """
        Args:
            app_context: Application context (for the event bus).
            sketch: The sketch to delete from.
            element_ids: Ids of the elements to delete.
        """
        super().__init__()
        self.app_context = app_context
        self.sketch = sketch
        self.element_ids = list(dict.fromkeys(element_ids))
        # (layer_id, index, element) in ascending index order per layer,
        # the order that restores the original positions on undo.
        self._removed: list[tuple[str, int, SketchElement]] = []

    def _remove_all(self) -> list[tuple[str, int, SketchElement]] | None:
        """Remove every element, or nothing if any id is missing."""
        if any(self.sketch.find_element(element_id) is None for element_id in self.element_ids):
            return None
        positions = []
        for element_id in self.element_ids:
            found = self.sketch.find_element(element_id)
            assert found is not None
            layer, element = found
            positions.append((layer.id, layer.elements.index(element), element_id))
        # Remove from the highest index down, so each removal leaves the
        # recorded indices of the remaining ones unchanged.
        removed = []
        for layer_id, _index, element_id in sorted(positions, key=lambda entry: entry[1], reverse=True):
            _layer, element, index = self.sketch.remove_element(element_id)
            removed.append((layer_id, index, element))
        removed.reverse()
        return removed

    @override
    def execute(self) -> CommandResult:
        if not self.element_ids:
            return CommandResult.NOOP
        locked = locked_element_ids(self.sketch, self.element_ids)
        if locked:
            self.logger.warning("Cannot delete elements on locked layers: %s", locked)
            return CommandResult.FAILURE
        removed = self._remove_all()
        if removed is None:
            self.logger.warning("Cannot delete: not every element of %s is in sketch '%s'", self.element_ids, self.sketch.id)
            return CommandResult.FAILURE
        self._removed = removed
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        if not self._removed:
            return CommandResult.FAILURE
        if any(self.sketch.get_layer(layer_id) is None for layer_id, _index, _element in self._removed):
            self.logger.warning("Cannot undo delete: a layer of the deleted elements is gone from sketch '%s'", self.sketch.id)
            return CommandResult.FAILURE
        if any(self.sketch.find_element(element.id) is not None for _layer_id, _index, element in self._removed):
            self.logger.warning("Cannot undo delete: a deleted element is already back in sketch '%s'", self.sketch.id)
            return CommandResult.FAILURE
        for layer_id, index, element in self._removed:
            self.sketch.add_element(layer_id, element, index)
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        if not self._removed:
            return CommandResult.FAILURE
        removed = self._remove_all()
        if removed is None:
            self.logger.warning("Cannot redo delete: not every element of %s is in sketch '%s'", self.element_ids, self.sketch.id)
            return CommandResult.FAILURE
        self._removed = removed
        emit_sketch_changed(self.app_context, self.sketch)
        return CommandResult.SUCCESS

    @override
    def cleanup(self) -> None:
        self._removed = []
