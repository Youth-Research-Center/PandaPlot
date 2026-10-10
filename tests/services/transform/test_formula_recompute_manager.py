"""Tests for live formula-column recompute (#154).

The manager listens on the real event bus, so these tests drive it the way the
app does: run a command that changes a dataset, and check what the formula
columns hold afterwards.
"""

from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.edit_command import EditCommand
from pandaplot.commands.project.dataset.transform_column_command import TransformColumnCommand
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.formula_column import FormulaColumnSpec
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.transform.formula_recompute_manager import FormulaRecomputeManager


@pytest.fixture
def env():
    """A dataset with a=[1,2,3] wired to a real event bus and manager."""
    project = Project(name="P")
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"a": [1.0, 2.0, 3.0]}))
    project.add_item(dataset)

    event_bus = EventBus()
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = event_bus

    manager = FormulaRecomputeManager(event_bus, app_state)

    app_context = Mock(spec=AppContext)
    app_context.app_state = app_state
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    app_context.event_bus = event_bus
    return app_context, dataset, manager


def _add_formula_column(dataset: Dataset, name: str, expression: str, sources: list[str],
                        values: list[float], *, live: bool) -> None:
    """Attach a formula column with pre-seeded values, as a transform would."""
    df = dataset.data.copy()
    df[name] = values
    dataset.set_data(df)
    dataset.set_formula_column(dataset.column_id(name), FormulaColumnSpec(
        expression=expression,
        transform_type="column" if len(sources) == 1 else "multi_column",
        source_column_ids=[dataset.column_id(source) for source in sources],
        live=live,
    ))


def _edit(app_context, dataset, row: int, column: int, old_value, new_value) -> EditCommand:
    command = EditCommand(app_context, dataset.id, (row, column), old_value, new_value)
    assert command.execute() is CommandResult.SUCCESS
    return command


class TestLiveRecompute:
    def test_editing_a_source_cell_recomputes_a_live_formula_column(self, env):
        app_context, dataset, _ = env
        _add_formula_column(dataset, "b", "x * 2", ["a"], [2.0, 4.0, 6.0], live=True)

        _edit(app_context, dataset, 0, 0, 1.0, 10.0)

        assert list(dataset.data["b"]) == [20.0, 4.0, 6.0]

    def test_a_non_live_formula_column_does_not_change_silently(self, env):
        app_context, dataset, _ = env
        _add_formula_column(dataset, "b", "x * 2", ["a"], [2.0, 4.0, 6.0], live=False)

        _edit(app_context, dataset, 0, 0, 1.0, 10.0)

        # Still the values the one-shot transform wrote; it's static data
        # until the user re-runs the transform.
        assert list(dataset.data["b"]) == [2.0, 4.0, 6.0]

    def test_a_plain_column_is_untouched(self, env):
        app_context, dataset, _ = env
        df = dataset.data.copy()
        df["note"] = ["x", "y", "z"]
        dataset.set_data(df)
        _add_formula_column(dataset, "b", "x * 2", ["a"], [2.0, 4.0, 6.0], live=True)

        _edit(app_context, dataset, 0, 0, 1.0, 10.0)

        assert list(dataset.data["note"]) == ["x", "y", "z"]

    def test_a_live_column_that_does_not_read_the_edited_column_is_not_recomputed(self, env):
        app_context, dataset, _ = env
        df = dataset.data.copy()
        df["other"] = [5.0, 5.0, 5.0]
        dataset.set_data(df)
        _add_formula_column(dataset, "b", "x * 2", ["other"], [10.0, 10.0, 10.0], live=True)
        # Deliberately stale values: if 'b' were recomputed they'd become 10s
        # again, so seed something else and prove it survives.
        dataset.data.loc[:, "b"] = [99.0, 99.0, 99.0]

        _edit(app_context, dataset, 0, 0, 1.0, 10.0)  # edits column 'a'

        assert list(dataset.data["b"]) == [99.0, 99.0, 99.0]


class TestCascade:
    def test_multi_hop_chain_recomputes_in_dependency_order(self, env):
        """A -> B -> C: editing A must leave C consistent with the *new* B,
        which only holds if B is recomputed before C."""
        app_context, dataset, _ = env
        _add_formula_column(dataset, "b", "x * 2", ["a"], [2.0, 4.0, 6.0], live=True)
        _add_formula_column(dataset, "c", "x + 1", ["b"], [3.0, 5.0, 7.0], live=True)

        _edit(app_context, dataset, 0, 0, 1.0, 10.0)

        assert list(dataset.data["b"]) == [20.0, 4.0, 6.0]
        assert list(dataset.data["c"]) == [21.0, 5.0, 7.0]

    def test_a_non_live_link_stops_the_cascade(self, env):
        """A -> B (not live) -> C (live): B is static, so nothing downstream
        of it has changed and C must not be recomputed off a stale B."""
        app_context, dataset, _ = env
        _add_formula_column(dataset, "b", "x * 2", ["a"], [2.0, 4.0, 6.0], live=False)
        _add_formula_column(dataset, "c", "x + 1", ["b"], [3.0, 5.0, 7.0], live=True)

        _edit(app_context, dataset, 0, 0, 1.0, 10.0)

        assert list(dataset.data["b"]) == [2.0, 4.0, 6.0]
        assert list(dataset.data["c"]) == [3.0, 5.0, 7.0]

    def test_recompute_does_not_re_enter_on_its_own_events(self, env):
        """The manager writes and emits data-changed for what it recomputed;
        without the reentrancy guard that would restart the cascade."""
        app_context, dataset, manager = env
        _add_formula_column(dataset, "b", "x * 2", ["a"], [2.0, 4.0, 6.0], live=True)

        calls = []
        original = manager.recompute
        manager.recompute = lambda *args, **kwargs: (calls.append(1), original(*args, **kwargs))[1]

        _edit(app_context, dataset, 0, 0, 1.0, 10.0)

        assert len(calls) == 1


class TestUndo:
    def test_undoing_a_source_edit_reverts_the_dependent_live_column(self, env):
        """Undo needs no special casing: EditCommand.undo() re-emits the same
        event, so the cascade runs backwards on its own."""
        app_context, dataset, _ = env
        _add_formula_column(dataset, "b", "x * 2", ["a"], [2.0, 4.0, 6.0], live=True)

        command = _edit(app_context, dataset, 0, 0, 1.0, 10.0)
        assert list(dataset.data["b"]) == [20.0, 4.0, 6.0]

        assert command.undo() is CommandResult.SUCCESS

        assert list(dataset.data["a"]) == [1.0, 2.0, 3.0]
        assert list(dataset.data["b"]) == [2.0, 4.0, 6.0]

    def test_redo_reapplies_the_cascade(self, env):
        app_context, dataset, _ = env
        _add_formula_column(dataset, "b", "x * 2", ["a"], [2.0, 4.0, 6.0], live=True)

        command = _edit(app_context, dataset, 0, 0, 1.0, 10.0)
        command.undo()

        assert command.redo() is CommandResult.SUCCESS
        assert list(dataset.data["b"]) == [20.0, 4.0, 6.0]


class TestEndToEnd:
    def test_transform_then_edit_recomputes_the_live_column(self, env):
        """The real user path: create a live formula column through the
        Transform panel's command, then edit a source cell."""
        app_context, dataset, _ = env
        assert TransformColumnCommand(app_context, "ds-1", {
            "new_column_name": "a_x2", "transform_type": "column", "source_columns": ["a"],
            "expression": "value * 2", "as_formula": True, "live": True,
        }).execute() is CommandResult.SUCCESS
        assert list(dataset.data["a_x2"]) == [2.0, 4.0, 6.0]

        _edit(app_context, dataset, 0, 0, 1.0, 10.0)

        assert list(dataset.data["a_x2"]) == [20.0, 4.0, 6.0]

    def test_transform_without_the_live_flag_stays_static(self, env):
        app_context, dataset, _ = env
        TransformColumnCommand(app_context, "ds-1", {
            "new_column_name": "a_x2", "transform_type": "column", "source_columns": ["a"],
            "expression": "value * 2", "as_formula": True,
        }).execute()

        _edit(app_context, dataset, 0, 0, 1.0, 10.0)

        assert list(dataset.data["a_x2"]) == [2.0, 4.0, 6.0]


class TestRobustness:
    def test_a_failing_expression_leaves_the_column_alone(self, env):
        app_context, dataset, _ = env
        _add_formula_column(dataset, "b", "1 / 0", ["a"], [2.0, 4.0, 6.0], live=True)

        _edit(app_context, dataset, 0, 0, 1.0, 10.0)

        assert list(dataset.data["b"]) == [2.0, 4.0, 6.0]

    def test_a_circular_registry_is_refused_rather_than_looping(self, env):
        """Cycles are rejected at creation time, so this can only come from a
        corrupted project file -- it must not hang or recurse forever."""
        app_context, dataset, _ = env
        _add_formula_column(dataset, "b", "x * 2", ["a"], [2.0, 4.0, 6.0], live=True)
        _add_formula_column(dataset, "c", "x + 1", ["b"], [3.0, 5.0, 7.0], live=True)
        # Make b read c, closing the loop.
        dataset.formula_column(dataset.column_id("b")).source_column_ids = [dataset.column_id("c")]

        _edit(app_context, dataset, 0, 0, 1.0, 10.0)

        assert list(dataset.data["b"]) == [2.0, 4.0, 6.0]
        assert list(dataset.data["c"]) == [3.0, 5.0, 7.0]

    def test_no_formula_columns_means_no_work(self, env):
        app_context, dataset, _ = env

        _edit(app_context, dataset, 0, 0, 1.0, 10.0)

        assert list(dataset.data["a"]) == [10.0, 2.0, 3.0]
