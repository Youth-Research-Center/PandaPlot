"""Tests for RecomputeFormulaColumnsCommand (#154): on-demand recompute of non-live formula columns."""

from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.recompute_formula_columns_command import RecomputeFormulaColumnsCommand
from pandaplot.commands.project.dataset.transform_column_command import TransformColumnCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def ctx():
    project = Project(name="P")
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"a": [1.0, 2.0, 3.0]}))
    project.add_item(dataset)

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.app_state = app_state
    app_state.event_bus = Mock()
    app_context.app_state = app_state
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = app_state.event_bus
    app_context.get_ui_controller.return_value = Mock(spec=UIController)
    return app_context, dataset


def _add_formula(app_context, name, expression, *, source="a", live=False):
    config = {
        "new_column_name": name,
        "transform_type": "column",
        "source_columns": [source],
        "expression": expression,
        "as_formula": True,
        "live": live,
    }
    assert TransformColumnCommand(app_context, "ds-1", config).execute() is CommandResult.SUCCESS


def _position(dataset, name):
    return list(dataset.data.columns).index(name)


def _data_changed(app_context):
    event_bus = app_context.event_bus
    return [c for c in event_bus.emit.call_args_list if c.args and c.args[0] == DatasetEvents.DATASET_DATA_CHANGED]


class TestRecomputeFormulaColumnsCommand:
    def test_recomputes_a_stale_non_live_column_from_current_sources(self, ctx):
        app_context, dataset = ctx
        _add_formula(app_context, "b", "x * 2")
        dataset.data.loc[0, "a"] = 10.0

        command = RecomputeFormulaColumnsCommand(app_context, "ds-1", [_position(dataset, "b")])
        assert command.execute() is CommandResult.SUCCESS
        assert list(dataset.data["b"]) == [20.0, 4.0, 6.0]
        assert list(dataset.data["a"]) == [10.0, 2.0, 3.0]
        assert dataset.formula_column_by_name("b") is not None

    def test_emits_data_changed_for_the_recomputed_column(self, ctx):
        app_context, dataset = ctx
        _add_formula(app_context, "b", "x * 2")
        dataset.data.loc[0, "a"] = 10.0
        app_context.event_bus.emit.reset_mock()

        RecomputeFormulaColumnsCommand(app_context, "ds-1", [_position(dataset, "b")]).execute()
        payloads = [c.args[1] for c in _data_changed(app_context)]
        assert [(p["dataset_id"], p["start_index"][1], p["end_index"][1]) for p in payloads] == [("ds-1", 1, 1)]

    def test_up_to_date_column_is_a_noop(self, ctx):
        app_context, dataset = ctx
        _add_formula(app_context, "b", "x * 2")
        app_context.event_bus.emit.reset_mock()

        assert RecomputeFormulaColumnsCommand(app_context, "ds-1", [_position(dataset, "b")]).execute() is CommandResult.NOOP
        assert not _data_changed(app_context)

    def test_plain_and_live_columns_are_ignored(self, ctx):
        app_context, dataset = ctx
        _add_formula(app_context, "live_b", "x * 2", live=True)
        before = dataset.data.copy()
        positions = [_position(dataset, "a"), _position(dataset, "live_b")]

        assert RecomputeFormulaColumnsCommand(app_context, "ds-1", positions).execute() is CommandResult.NOOP
        pd.testing.assert_frame_equal(dataset.data, before)

    def test_selected_dependents_are_recomputed_after_their_sources(self, ctx):
        app_context, dataset = ctx
        _add_formula(app_context, "b", "x * 2")
        _add_formula(app_context, "c", "x + 1", source="b")
        dataset.data.loc[0, "a"] = 10.0

        # Dependent listed first: the order must come from the dependency graph.
        positions = [_position(dataset, "c"), _position(dataset, "b")]
        assert RecomputeFormulaColumnsCommand(app_context, "ds-1", positions).execute() is CommandResult.SUCCESS
        assert list(dataset.data["b"]) == [20.0, 4.0, 6.0]
        assert list(dataset.data["c"]) == [21.0, 5.0, 7.0]

    def test_undo_and_redo_restore_the_values(self, ctx):
        app_context, dataset = ctx
        _add_formula(app_context, "b", "x * 2")
        dataset.data.loc[0, "a"] = 10.0
        command = RecomputeFormulaColumnsCommand(app_context, "ds-1", [_position(dataset, "b")])
        assert command.execute() is CommandResult.SUCCESS

        assert command.undo() is CommandResult.SUCCESS
        assert list(dataset.data["b"]) == [2.0, 4.0, 6.0]
        assert command.redo() is CommandResult.SUCCESS
        assert list(dataset.data["b"]) == [20.0, 4.0, 6.0]

    def test_redo_replays_the_first_result_without_reevaluating(self, ctx):
        app_context, dataset = ctx
        _add_formula(app_context, "b", "x * 2")
        dataset.data.loc[0, "a"] = 10.0
        command = RecomputeFormulaColumnsCommand(app_context, "ds-1", [_position(dataset, "b")])
        command.execute()
        command.undo()
        dataset.data.loc[0, "a"] = 99.0

        assert command.redo() is CommandResult.SUCCESS
        assert list(dataset.data["b"]) == [20.0, 4.0, 6.0]

    def test_failing_formula_changes_nothing_and_tells_the_user(self, ctx):
        app_context, dataset = ctx
        _add_formula(app_context, "b", "x * 2")
        _add_formula(app_context, "c", "x + 1", source="b")
        dataset.data.loc[0, "a"] = 10.0
        dataset.formula_column_by_name("c").expression = "undefined_name + 1"
        before = dataset.data.copy()

        positions = [_position(dataset, "b"), _position(dataset, "c")]
        command = RecomputeFormulaColumnsCommand(app_context, "ds-1", positions)
        assert command.execute() is CommandResult.FAILURE
        pd.testing.assert_frame_equal(dataset.data, before)
        app_context.get_ui_controller().show_warning_message.assert_called_once()
        assert command.undo() is CommandResult.FAILURE

    def test_missing_source_column_is_refused(self, ctx):
        app_context, dataset = ctx
        _add_formula(app_context, "b", "x * 2")
        dataset.formula_column_by_name("b").source_column_ids = ["gone"]

        command = RecomputeFormulaColumnsCommand(app_context, "ds-1", [_position(dataset, "b")])
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller().show_warning_message.assert_called_once()

    def test_unknown_dataset_fails(self, ctx):
        app_context, _ = ctx
        assert RecomputeFormulaColumnsCommand(app_context, "nope", [0]).execute() is CommandResult.FAILURE

    def test_undo_is_aborted_when_the_column_was_deleted_meanwhile(self, ctx):
        app_context, dataset = ctx
        _add_formula(app_context, "b", "x * 2")
        dataset.data.loc[0, "a"] = 10.0
        command = RecomputeFormulaColumnsCommand(app_context, "ds-1", [_position(dataset, "b")])
        command.execute()
        dataset.set_data(dataset.data.drop(columns=["b"]))

        assert command.undo() is CommandResult.ABORTED

    def test_cleanup_drops_retained_state(self, ctx):
        app_context, dataset = ctx
        _add_formula(app_context, "b", "x * 2")
        dataset.data.loc[0, "a"] = 10.0
        command = RecomputeFormulaColumnsCommand(app_context, "ds-1", [_position(dataset, "b")])
        command.execute()

        command.cleanup()
        assert command.dataset is None
        assert command.undo() is CommandResult.FAILURE
