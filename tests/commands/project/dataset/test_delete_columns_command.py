"""Tests for DeleteColumnsCommand (column drop + chart-reference cascade)."""

import logging
from collections import OrderedDict
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.commands.project.dataset.delete_columns_command import DeleteColumnsCommand
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style.line import LineSeriesStyle
from pandaplot.models.chart.series_style.vector import VectorSeriesStyle
from pandaplot.models.events.event_types import ChartEvents, DatasetOperationEvents
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset
from pandaplot.models.project.items.chart import resolve_series_column


@pytest.fixture
def env():
    project = Project("P")
    dataset = Dataset(name="ds", data=pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6], "d": [7, 8]}))
    other = Dataset(name="other", data=pd.DataFrame({"a": [7]}))
    project.add_item(dataset)
    project.add_item(other)

    # Series/fits reference columns by stable id (the caller resolves names).
    chart = Chart(name="c")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("a"),
                          y_column_id=dataset.column_id("b"), label="s1")
    chart.add_data_series(other.id, x_column_id=other.column_id("a"),  # other dataset: must not be touched
                          y_column_id=other.column_id("a"), label="s2")
    chart.add_fit_data(dataset.id, "Linear", np.array([1.0]), np.array([2.0]),
                       source_x_column_id=dataset.column_id("a"),
                       source_y_column_id=dataset.column_id("b"))
    project.add_item(chart)

    untouched_chart = Chart(name="c2")
    untouched_chart.add_data_series(dataset.id, x_column_id=dataset.column_id("c"),  # unrelated column: unaffected
                                    y_column_id=dataset.column_id("c"), label="s3")
    project.add_item(untouched_chart)

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    ui_controller = Mock()
    ui_controller.show_confirmation.return_value = True
    app_context.get_ui_controller.return_value = ui_controller
    app_context.event_bus = Mock()
    app_state.event_bus = app_context.event_bus
    return app_context, dataset, other, chart, untouched_chart


def _chart_updated_calls(app_context):
    return [c for c in app_context.event_bus.emit.call_args_list
            if c.args[0] == ChartEvents.CHART_UPDATED]


def test_delete_removes_column_and_cascades_referencing_series_and_fits(env):
    app_context, dataset, other, chart, untouched_chart = env
    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])

    assert command.execute() is True
    assert list(dataset.data.columns) == ["b", "c", "d"]
    assert len(chart.data_series) == 1  # s1 (column 'a') removed, s2 (other dataset) kept
    assert chart.data_series[0].label == "s2"
    assert chart.fit_data == []
    # unrelated-column chart is untouched
    s3 = untouched_chart.data_series[0]
    assert resolve_series_column(dataset, s3.x_column_id, s3.x_column) == "c"


def test_delete_with_no_chart_references_skips_confirmation(env):
    app_context, dataset, _, _, untouched_chart = env
    ui_controller = app_context.get_ui_controller.return_value
    command = DeleteColumnsCommand(app_context, dataset.id, ["d"])

    assert command.execute() is True
    ui_controller.show_confirmation.assert_not_called()
    s3 = untouched_chart.data_series[0]  # unaffected
    assert resolve_series_column(dataset, s3.x_column_id, s3.x_column) == "c"


def test_delete_declined_confirmation_aborts(env):
    app_context, dataset, _, chart, _ = env
    ui_controller = app_context.get_ui_controller.return_value
    ui_controller.show_confirmation.return_value = False
    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])

    assert command.execute() is False
    assert list(dataset.data.columns) == ["a", "b", "c", "d"]
    assert len(chart.data_series) == 2


def test_undo_restores_data_and_chart_references(env):
    app_context, dataset, _, chart, _ = env
    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])
    command.execute()

    assert command.undo() is True
    assert list(dataset.data.columns) == ["a", "b", "c", "d"]
    assert len(chart.data_series) == 2
    # After undo, the restored column keeps its id so the series resolves again.
    s1 = chart.data_series[0]
    assert resolve_series_column(dataset, s1.x_column_id, s1.x_column) == "a"
    assert len(chart.fit_data) == 1


def test_redo_reapplies_deletion_and_removes_references_again(env):
    app_context, dataset, _, chart, _ = env
    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])
    command.execute()
    command.undo()

    assert command.redo() is True
    assert list(dataset.data.columns) == ["b", "c", "d"]
    assert len(chart.data_series) == 1
    assert chart.data_series[0].label == "s2"
    assert chart.fit_data == []


def test_redo_failure_surfaces_error_message(env):
    app_context, dataset, _, chart, _ = env
    ui_controller = app_context.get_ui_controller.return_value
    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])
    command.execute()
    command.undo()

    # Simulate the dataset having changed out from under the command since undo
    # (e.g. another operation already removed the column), so the drop() in
    # redo's _perform_deletion raises instead of silently succeeding.
    dataset.set_data(dataset.data.drop(columns=["a"]))

    assert command.redo() is False
    ui_controller.show_error_message.assert_called_once()


def test_events_emitted_only_for_affected_charts(env):
    app_context, dataset, _, chart, untouched_chart = env
    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])
    command.execute()

    removed_calls = [c for c in app_context.event_bus.emit.call_args_list
                      if c.args[0] == DatasetOperationEvents.DATASET_COLUMN_REMOVED]
    assert len(removed_calls) == 1

    updated = _chart_updated_calls(app_context)
    assert len(updated) == 1  # 'untouched_chart' has no reference to column 'a'
    assert updated[0].args[1]["chart_id"] == chart.id


def test_delete_u_column_removes_vector_series(env):
    """A vector series' U/V columns are required (like x/y), so deleting
    either removes the whole series rather than just clearing a reference."""
    app_context, dataset, _, _, _ = env
    vector_chart = Chart(name="vc", chart_type="vector")
    vector_chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("c"), y_column_id=dataset.column_id("c"),
        label="v1",
        style=VectorSeriesStyle(u_column_id=dataset.column_id("a"), v_column_id=dataset.column_id("b")),
    )
    app_context.get_app_state.return_value.current_project.add_item(vector_chart)

    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])

    assert command.execute() is True
    assert vector_chart.data_series == []


def test_delete_magnitude_column_clears_reference_but_keeps_series(env):
    """magnitude is optional -- a vector series still renders without it, so
    deleting its column only clears the reference (mirrors error columns)."""
    app_context, dataset, _, _, _ = env
    vector_chart = Chart(name="vc", chart_type="vector")
    vector_chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("c"), y_column_id=dataset.column_id("c"),
        label="v1",
        style=VectorSeriesStyle(
            u_column_id=dataset.column_id("c"), v_column_id=dataset.column_id("c"),
            magnitude_column_id=dataset.column_id("a"),
        ),
    )
    app_context.get_app_state.return_value.current_project.add_item(vector_chart)

    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])

    assert command.execute() is True
    assert len(vector_chart.data_series) == 1
    series = vector_chart.data_series[0]
    assert series.style.magnitude_column_id == ""
    assert series.style.magnitude_column == ""


def test_undo_restores_a_cleared_magnitude_reference(env):
    app_context, dataset, _, _, _ = env
    vector_chart = Chart(name="vc", chart_type="vector")
    vector_chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("c"), y_column_id=dataset.column_id("c"),
        label="v1",
        style=VectorSeriesStyle(
            u_column_id=dataset.column_id("c"), v_column_id=dataset.column_id("c"),
            magnitude_column_id=dataset.column_id("a"),
        ),
    )
    app_context.get_app_state.return_value.current_project.add_item(vector_chart)
    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])
    command.execute()

    assert command.undo() is True
    series = vector_chart.data_series[0]
    assert resolve_series_column(dataset, series.style.magnitude_column_id, series.style.magnitude_column) == "a"


def test_delete_error_bar_column_clears_reference_but_keeps_series(env):
    """error bars are optional -- a Line series still renders without them, so
    deleting the referenced column only clears the error-bar reference."""
    app_context, dataset, _, _, _ = env
    line_chart = Chart(name="lc")
    line_chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("c"), y_column_id=dataset.column_id("c"),
        label="l1",
        style=LineSeriesStyle(error_bars=ErrorBarConfig(y_error_column_id=dataset.column_id("a"))),
    )
    app_context.get_app_state.return_value.current_project.add_item(line_chart)

    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])

    assert command.execute() is True
    assert len(line_chart.data_series) == 1
    series = line_chart.data_series[0]
    assert series.style.error_bars.y_error_column_id == ""
    assert series.style.error_bars.y_error_column == ""


def test_execute_logs_a_warning_when_no_column_specs(env, caplog):
    app_context, dataset, _, _, _ = env
    command = DeleteColumnsCommand(app_context, dataset.id, [])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "no column specs" in caplog.text.lower()


def test_execute_logs_a_warning_when_no_project_open(env, caplog):
    app_context, dataset, _, _, _ = env
    app_context.get_app_state.return_value.has_project = False
    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "no project" in caplog.text.lower()


def test_execute_logs_a_warning_when_dataset_not_found(env, caplog):
    app_context, dataset, _, _, _ = env
    command = DeleteColumnsCommand(app_context, "missing-ds", ["a"])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "missing-ds" in caplog.text


def test_execute_logs_a_warning_when_item_is_not_a_dataset(env, caplog):
    app_context, dataset, _, chart, _ = env
    # 'chart' is already registered in the project (see env fixture) but is a
    # Chart, not a Dataset.
    command = DeleteColumnsCommand(app_context, chart.id, ["a"])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert chart.id in caplog.text


def test_execute_logs_a_warning_when_dataset_is_empty(env, caplog):
    import pandas as pd

    from pandaplot.models.project.items import Dataset

    app_context, _, _, _, _ = env
    empty_ds = Dataset(name="empty", data=pd.DataFrame())
    app_context.get_app_state.return_value.current_project.add_item(empty_ds)
    command = DeleteColumnsCommand(app_context, empty_ds.id, ["a"])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert empty_ds.id in caplog.text


def test_execute_logs_a_warning_when_no_valid_columns_resolved(env, caplog):
    app_context, dataset, _, _, _ = env
    command = DeleteColumnsCommand(app_context, dataset.id, [999])  # out-of-range position

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert dataset.id in caplog.text


def test_execute_logs_a_warning_when_columns_missing(env, caplog, monkeypatch):
    # _resolve_columns() already filters out names that don't exist at
    # resolution time, so the "missing columns" check in execute() only
    # guards against the column disappearing between resolution and this
    # check (e.g. a race). Force that by stubbing _resolve_columns() to
    # report a column that isn't actually in the dataset.
    app_context, dataset, _, _, _ = env
    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])

    def _fake_resolve():
        command.column_names = ["ghost"]
        command.column_positions = [0]

    monkeypatch.setattr(command, "_resolve_columns", _fake_resolve)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "ghost" in caplog.text


def test_execute_logs_a_warning_when_duplicate_column_names(env, caplog):
    app_context, dataset, _, _, _ = env
    command = DeleteColumnsCommand(app_context, dataset.id, ["a", "a"])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert dataset.id in caplog.text


def test_execute_logs_a_warning_when_deleting_all_columns(env, caplog):
    app_context, dataset, _, _, _ = env
    command = DeleteColumnsCommand(app_context, dataset.id, ["a", "b", "c", "d"])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert dataset.id in caplog.text


def test_undo_restores_a_cleared_error_bar_reference(env):
    app_context, dataset, _, _, _ = env
    line_chart = Chart(name="lc")
    line_chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("c"), y_column_id=dataset.column_id("c"),
        label="l1",
        style=LineSeriesStyle(error_bars=ErrorBarConfig(y_error_column_id=dataset.column_id("a"))),
    )
    app_context.get_app_state.return_value.current_project.add_item(line_chart)
    command = DeleteColumnsCommand(app_context, dataset.id, ["a"])
    command.execute()

    assert command.undo() is True
    series = line_chart.data_series[0]
    assert resolve_series_column(
        dataset, series.style.error_bars.y_error_column_id, series.style.error_bars.y_error_column
    ) == "a"


def test_cleanup_releases_the_undo_snapshots():
    app_context = Mock()
    app_context.get_app_state.return_value = Mock(has_project=True)
    app_context.get_ui_controller.return_value = Mock()

    command = DeleteColumnsCommand(app_context, "ds-1", ["a"])
    command.original_data = pd.DataFrame({"a": [1, 2, 3]})
    command.deleted_columns_data = {"a": pd.Series([1, 2, 3])}
    command.original_column_ids = OrderedDict({"a": "col-a"})
    command.removed_chart_refs = {"chart-1": {"series": [(0, Mock())], "fits": []}}
    command.cleared_error_refs = {"chart-1": [(0, [(Mock(), "y_error_column_id", "col-a")])]}

    command.cleanup()

    assert command.original_data is None
    assert command.deleted_columns_data is None
    assert command.original_column_ids is None
    assert command.removed_chart_refs == {}
    assert command.cleared_error_refs == {}
