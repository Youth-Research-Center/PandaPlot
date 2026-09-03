"""Tests for RenameColumnCommand.

Columns carry a stable id; series/fits reference the column by id, so a rename
updates only the dataset's id->name registry and the DataFrame. Series
references are *not* rewritten — they keep resolving to the new name via their
id (see resolve_series_column). The name fields are only a fallback and are
intentionally left untouched.
"""

import logging
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.rename_column_command import RenameColumnCommand
from pandaplot.models.chart.series_style.vector import VectorSeriesStyle
from pandaplot.models.events.event_types import ChartEvents, DatasetOperationEvents
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset
from pandaplot.models.project.items.chart import resolve_series_column


@pytest.fixture
def env():
    project = Project("P")
    dataset = Dataset(name="ds", data=pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
    other = Dataset(name="other", data=pd.DataFrame({"a": [5]}))
    project.add_item(dataset)
    project.add_item(other)

    # Series/fits reference columns by stable id (the caller resolves names).
    chart = Chart(name="c")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("a"),
                          y_column_id=dataset.column_id("b"), label="s1")
    chart.add_data_series(other.id, x_column_id=other.column_id("a"),  # other dataset: must not change
                          y_column_id=other.column_id("a"), label="s2")
    chart.add_fit_data(dataset.id, "Linear", np.array([1.0]), np.array([2.0]),
                       source_x_column_id=dataset.column_id("a"),
                       source_y_column_id=dataset.column_id("b"))
    project.add_item(chart)

    untouched_chart = Chart(name="c2")
    untouched_chart.add_data_series(other.id, x_column_id=other.column_id("a"),
                                    y_column_id=other.column_id("a"), label="s3")
    project.add_item(untouched_chart)

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    app_context.event_bus = Mock()
    return app_context, dataset, other, chart


def _chart_updated_calls(app_context):
    return [c for c in app_context.event_bus.emit.call_args_list
            if c.args[0] == ChartEvents.CHART_UPDATED]


def test_rename_updates_dataframe_and_series_resolve_via_id(env):
    app_context, dataset, other, chart = env
    s1 = chart.data_series[0]
    fit = chart.fit_data[0]
    x_id_before = s1.x_column_id

    command = RenameColumnCommand(app_context, dataset.id, 0, "time")

    assert command.execute() is CommandResult.SUCCESS
    assert list(dataset.data.columns) == ["time", "b"]
    # The series reference is untouched but resolves to the new name via its id.
    assert s1.x_column_id == x_id_before
    assert s1.x_column == ""  # new series hold no name; id is authoritative
    assert resolve_series_column(dataset, s1.x_column_id, s1.x_column) == "time"
    assert resolve_series_column(dataset, s1.y_column_id, s1.y_column) == "b"
    assert resolve_series_column(dataset, fit.source_x_column_id, fit.source_x_column) == "time"
    # same column name in another dataset: resolves to its own unchanged column
    assert resolve_series_column(other, chart.data_series[1].x_column_id,
                                 chart.data_series[1].x_column) == "a"
    assert list(other.data.columns) == ["a"]


def test_undo_and_redo_round_trip(env):
    app_context, dataset, _, chart = env
    s1 = chart.data_series[0]
    fit = chart.fit_data[0]
    command = RenameColumnCommand(app_context, dataset.id, 0, "time")
    command.execute()

    command.undo()
    assert list(dataset.data.columns) == ["a", "b"]
    assert resolve_series_column(dataset, s1.x_column_id, s1.x_column) == "a"
    assert resolve_series_column(dataset, fit.source_x_column_id, fit.source_x_column) == "a"

    command.redo()
    assert list(dataset.data.columns) == ["time", "b"]
    assert resolve_series_column(dataset, s1.x_column_id, s1.x_column) == "time"


def test_duplicate_name_rejected(env):
    app_context, dataset, _, _ = env
    command = RenameColumnCommand(app_context, dataset.id, 0, "b")
    assert command.execute() is CommandResult.FAILURE
    assert list(dataset.data.columns) == ["a", "b"]
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_duplicate_name_rejected_logs_a_warning(env, caplog):
    app_context, dataset, _, _ = env
    command = RenameColumnCommand(app_context, dataset.id, 0, "b")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "b" in caplog.text


def test_execute_logs_a_warning_when_no_project_open(env, caplog):
    app_context, dataset, _, _ = env
    app_context.get_app_state.return_value.has_project = False
    command = RenameColumnCommand(app_context, dataset.id, 0, "time")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert dataset.id in caplog.text


def test_execute_logs_a_warning_when_dataset_not_found(env, caplog):
    app_context, _, _, _ = env
    command = RenameColumnCommand(app_context, "missing-ds", 0, "time")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "missing-ds" in caplog.text


def test_execute_logs_a_warning_when_column_index_out_of_range(env, caplog):
    app_context, dataset, _, _ = env
    command = RenameColumnCommand(app_context, dataset.id, 5, "time")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "5" in caplog.text


def test_execute_logs_a_warning_when_new_name_is_empty(env, caplog):
    app_context, dataset, _, _ = env
    command = RenameColumnCommand(app_context, dataset.id, 0, "   ")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert dataset.id in caplog.text


def test_empty_name_rejected(env):
    app_context, dataset, _, _ = env
    command = RenameColumnCommand(app_context, dataset.id, 0, "   ")
    assert command.execute() is CommandResult.FAILURE
    assert list(dataset.data.columns) == ["a", "b"]


def test_unchanged_name_is_silent_noop(env):
    app_context, dataset, _, _ = env
    command = RenameColumnCommand(app_context, dataset.id, 0, "a")
    assert command.execute() is CommandResult.NOOP
    assert list(dataset.data.columns) == ["a", "b"]
    app_context.get_ui_controller.return_value.show_error_message.assert_not_called()


def test_undo_after_rejected_execute_is_a_noop(env):
    app_context, dataset, _, chart = env
    command = RenameColumnCommand(app_context, dataset.id, 0, "b")  # duplicate -> rejected
    assert command.execute() is CommandResult.FAILURE

    command.undo()  # CommandExecutor pushes commands even on failure; undo must not corrupt
    assert list(dataset.data.columns) == ["a", "b"]
    assert resolve_series_column(dataset, chart.data_series[0].y_column_id,
                                 chart.data_series[0].y_column) == "b"

    command.redo()
    assert list(dataset.data.columns) == ["a", "b"]


def test_events_emitted_only_for_affected_charts(env):
    app_context, dataset, _, chart = env
    command = RenameColumnCommand(app_context, dataset.id, 0, "time")
    command.execute()

    renamed_calls = [c for c in app_context.event_bus.emit.call_args_list
                     if c.args[0] == DatasetOperationEvents.DATASET_COLUMN_RENAMED]
    assert len(renamed_calls) == 1
    assert renamed_calls[0].args[1]["old_name"] == "a"
    assert renamed_calls[0].args[1]["new_name"] == "time"

    updated = _chart_updated_calls(app_context)
    assert len(updated) == 1  # 'untouched_chart' gets no event
    assert updated[0].args[1]["chart_id"] == chart.id
    assert "chart" in updated[0].args[1]


def test_events_emitted_for_a_vector_series_referencing_the_column_by_u_v_or_magnitude(env):
    """u/v/magnitude are vector-plot fields, added after this test file's
    original series/fit coverage above -- a chart whose only reference to
    the renamed column is via one of these fields must still be notified."""
    app_context, dataset, _, _ = env
    vector_chart = Chart(name="vc", chart_type="vector")
    vector_chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("b"), y_column_id=dataset.column_id("b"),
        label="v1",
        style=VectorSeriesStyle(
            u_column_id=dataset.column_id("a"), v_column_id=dataset.column_id("b"),
            magnitude_column_id=dataset.column_id("a"),
        ),
    )
    app_context.get_app_state.return_value.current_project.add_item(vector_chart)

    command = RenameColumnCommand(app_context, dataset.id, 0, "time")
    command.execute()

    updated = _chart_updated_calls(app_context)
    assert vector_chart.id in {call.args[1]["chart_id"] for call in updated}


def test_cleanup_releases_the_dataset_reference(env):
    app_context, dataset, _, _ = env
    command = RenameColumnCommand(app_context, dataset.id, 0, "time")
    command.execute()
    assert command.dataset is not None

    command.cleanup()

    assert command.dataset is None
