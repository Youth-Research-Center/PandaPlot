"""Tests for TransformColumnCommand: existing target, refresh events, undo,
and the undo() failure-path logging added for issue-184-audit-command-logging.
"""

import logging
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.transform_column_command import TransformColumnCommand
from pandaplot.models.events.event_types import DatasetEvents, DatasetOperationEvents
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
    return app_context, dataset, app_state.event_bus


def _emitted(event_bus, name):
    return [c.args[1] for c in event_bus.emit.call_args_list if c.args and c.args[0] == name]


def _config(new_name, expression="value * 2", *, replace=False):
    return {
        "new_column_name": new_name,
        "transform_type": "column",
        "source_columns": ["a"],
        "expression": expression,
        "replace_existing": replace,
    }


class TestTransformColumnCommand:
    def test_new_column_added_and_event(self, ctx):
        app_context, dataset, event_bus = ctx
        command = TransformColumnCommand(app_context, "ds-1", _config("a_x2"))
        assert command.execute() is CommandResult.SUCCESS
        assert list(dataset.data["a_x2"]) == [2.0, 4.0, 6.0]
        assert _emitted(event_bus, DatasetOperationEvents.DATASET_COLUMN_ADDED)

    def test_target_can_be_existing_column(self, ctx):
        app_context, dataset, event_bus = ctx
        command = TransformColumnCommand(app_context, "ds-1", _config("a", replace=True))
        assert command.execute() is CommandResult.SUCCESS
        # 'a' overwritten in place, no new column.
        assert list(dataset.data.columns) == ["a"]
        assert list(dataset.data["a"]) == [2.0, 4.0, 6.0]
        # Overwrite fires a data-changed (not column-added) event.
        assert _emitted(event_bus, DatasetEvents.DATASET_DATA_CHANGED)
        assert not _emitted(event_bus, DatasetOperationEvents.DATASET_COLUMN_ADDED)

    def test_existing_target_without_replace_fails(self, ctx):
        app_context, _, _ = ctx
        command = TransformColumnCommand(app_context, "ds-1", _config("a", replace=False))
        assert command.execute() is CommandResult.FAILURE
        assert "a" in command.error_message

    def test_expression_can_reference_the_source_column_via_cols_by_its_real_name(self, ctx):
        """Regression (#203): cols["name"] looks a column up by its real
        name, e.g. cols["a"] for a column literally named "a" -- a dict
        subscript alongside the generic x/value/column/data aliases."""
        app_context, dataset, _ = ctx
        command = TransformColumnCommand(app_context, "ds-1", _config("a_x2", expression='cols["a"] * 2'))
        assert command.execute() is CommandResult.SUCCESS
        assert list(dataset.data["a_x2"]) == [2.0, 4.0, 6.0]

    def test_cols_works_for_a_column_name_that_is_not_a_valid_python_identifier(self, ctx):
        """A column name with a space (or any other non-identifier name)
        could never be written as a bound variable at all -- cols[...] has
        no such restriction, since it's a string dict key, not an
        identifier."""
        app_context, dataset, _ = ctx
        dataset.data["my col"] = [10.0, 20.0, 30.0]
        command = TransformColumnCommand(app_context, "ds-1", {
            "new_column_name": "out", "transform_type": "column",
            "source_columns": ["my col"], "expression": 'cols["my col"] * 2', "replace_existing": False,
        })
        assert command.execute() is CommandResult.SUCCESS
        assert list(dataset.data["out"]) == [20.0, 40.0, 60.0]

    def test_cols_does_not_shadow_a_safe_globals_function_of_the_same_name(self, ctx):
        """Regression: a column literally named "log" (one of
        _create_safe_execution_environment's bare math names) must not
        shadow the global log() function the way binding "log" as a raw
        local variable would have -- cols["log"] reaches the column, while
        log(...) still reaches the function in the same expression."""
        app_context, dataset, _ = ctx
        dataset.data["log"] = [10.0, 20.0, 30.0]
        command = TransformColumnCommand(app_context, "ds-1", {
            "new_column_name": "combo", "transform_type": "column",
            "source_columns": ["log"], "expression": 'cols["log"] + log(1)', "replace_existing": False,
        })
        assert command.execute() is CommandResult.SUCCESS
        # log(1) == 0.0, so the result is exactly the column's own values --
        # proof log() still resolved to the function, not the column.
        assert list(dataset.data["combo"]) == [10.0, 20.0, 30.0]

    def test_expression_error_is_captured_in_error_message(self, ctx):
        app_context, _, _ = ctx
        command = TransformColumnCommand(app_context, "ds-1", _config("bad", expression="1 / 0"))
        assert command.execute() is CommandResult.FAILURE
        assert "division" in command.error_message.lower() or "zero" in command.error_message.lower()

    def test_undo_restores_replaced_column(self, ctx):
        app_context, dataset, _ = ctx
        original = list(dataset.data["a"])
        command = TransformColumnCommand(app_context, "ds-1", _config("a", replace=True))
        command.execute()
        assert command.undo() is CommandResult.SUCCESS
        assert list(dataset.data["a"]) == original

    def test_undo_removes_new_column(self, ctx):
        app_context, dataset, event_bus = ctx
        command = TransformColumnCommand(app_context, "ds-1", _config("a_x2"))
        command.execute()
        assert command.undo() is CommandResult.SUCCESS
        assert "a_x2" not in dataset.data.columns
        assert _emitted(event_bus, DatasetOperationEvents.DATASET_COLUMN_REMOVED)


def _make_command(app_context=None):
    app_context = app_context or Mock(spec=AppContext)
    return TransformColumnCommand(
        app_context, "ds-1",
        {
            "new_column_name": "result",
            "transform_type": "column",
            "source_columns": ["a"],
            "expression": "value * 2",
        },
    )


def test_undo_logs_a_warning_when_dataset_not_set(caplog):
    command = _make_command()
    # undo() called without a prior successful execute(): self.dataset is None.

    with caplog.at_level(logging.WARNING):
        assert command.undo() is CommandResult.FAILURE
    assert "ds-1" in caplog.text


def test_undo_logs_a_warning_when_dataset_has_no_data(caplog):
    command = _make_command()
    dataset = Mock(spec=Dataset)
    dataset.data = None
    command.dataset = dataset

    with caplog.at_level(logging.WARNING):
        assert command.undo() is CommandResult.FAILURE
    assert "ds-1" in caplog.text


def test_cleanup_releases_the_original_data_snapshot():
    app_context = Mock(spec=AppContext)

    command = TransformColumnCommand(app_context, "ds-1", {
        "new_column_name": "a_x2",
        "transform_type": "column",
        "source_columns": ["a"],
        "expression": "value * 2",
        "replace_existing": False,
    })
    command.original_data = pd.Series([1, 2, 3])

    command.cleanup()

    assert command.original_data is None
