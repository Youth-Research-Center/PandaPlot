"""Tests for AnalysisCommand (dispatch) and ApplyAnalysisResultCommand
(the actual, undo-tracked mutation)."""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.project.dataset.analysis_command import AnalysisCommand
from pandaplot.commands.project.dataset.apply_analysis_result_command import ApplyAnalysisResultCommand
from pandaplot.models.events.event_types import DatasetEvents, DatasetOperationEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState

from tests.commands.project.conftest import SyncTaskScheduler


@pytest.fixture
def ctx():
    project = Project(name="P")
    x = np.linspace(0.0, 10.0, 11)
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"x": x, "y": x ** 2}))
    project.add_item(dataset)

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_task_scheduler.return_value = SyncTaskScheduler()
    app_context.get_command_executor.return_value = CommandExecutor()
    return app_context, project, dataset, app_state.event_bus


def _emitted(event_bus, event_name):
    """Return payloads emitted for a given event name."""
    return [
        call.args[1]
        for call in event_bus.emit.call_args_list
        if call.args and call.args[0] == event_name
    ]


class TestAnalysisCommand:
    def test_full_length_derivative_added(self, ctx):
        app_context, _, dataset, event_bus = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        assert command.execute() is CommandResult.SUCCESS
        assert "dydx" in dataset.data.columns
        # d/dx of x^2 = 2x; check away from the noisy endpoints.
        assert dataset.data["dydx"].iloc[5] == pytest.approx(10.0, abs=0.1)
        assert dataset.data["dydx"].notna().all()

        added = _emitted(event_bus, DatasetOperationEvents.DATASET_COLUMN_ADDED)
        assert added and added[0]["column_positions"] == [2]

    def test_segment_result_aligns_to_source_rows(self, ctx):
        app_context, _, dataset, _ = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "integral", "x_column": "x", "y_column": "y",
            "new_column_name": "cum", "parameters": {"start_index": 3, "end_index": 8},
        })
        assert command.execute() is CommandResult.SUCCESS

        col = dataset.data["cum"]
        assert col.iloc[:3].isna().all()
        assert col.iloc[8:].isna().all()
        assert col.iloc[3:8].notna().all()
        assert col.iloc[3] == pytest.approx(0.0)

    def test_replace_existing_emits_data_changed(self, ctx):
        app_context, _, dataset, event_bus = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "y", "replace_existing": True,
        })
        assert command.execute() is CommandResult.SUCCESS
        assert list(dataset.data.columns) == ["x", "y"]

        changed = _emitted(event_bus, DatasetEvents.DATASET_DATA_CHANGED)
        assert changed and changed[0]["start_index"][1] == 1
        assert not _emitted(event_bus, DatasetOperationEvents.DATASET_COLUMN_ADDED)

    def test_dataset_not_found_is_surfaced_to_the_user(self, ctx):
        app_context, _, _, _ = ctx
        command = AnalysisCommand(app_context, "missing-ds", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_dataset_with_no_data_is_surfaced_to_the_user(self, ctx):
        app_context, _, dataset, _ = ctx
        dataset.data = None
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_existing_target_without_replace_fails(self, ctx):
        app_context, _, _, _ = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "y", "replace_existing": False,
        })
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_analysis_engine_failure_is_surfaced_via_on_complete(self, ctx, monkeypatch):
        """The engine failure now happens on the (synchronous, in tests)
        background task, so execute() itself still reports SUCCESS -- it only
        means "dispatched". The failure surfaces through on_complete."""
        app_context, _, _, _ = ctx
        monkeypatch.setattr(
            "pandaplot.commands.project.dataset.analysis_command.AnalysisEngine.calculate_derivative",
            Mock(side_effect=ValueError("boom")),
        )
        outcomes = []
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        }, on_complete=outcomes.append)

        assert command.execute() is CommandResult.SUCCESS  # dispatched
        assert outcomes == [CommandResult.FAILURE]
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
        title, message = app_context.get_ui_controller.return_value.show_error_message.call_args.args
        assert "boom" in message

    def test_on_complete_reports_success_once_applied(self, ctx):
        app_context, _, _, _ = ctx
        outcomes = []
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        }, on_complete=outcomes.append)

        assert command.execute() is CommandResult.SUCCESS
        assert outcomes == [CommandResult.SUCCESS]

    def test_occupies_no_undo_slot(self, ctx):
        app_context, _, _, _ = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        assert command.occupies_undo_slot() is False

    def test_undo_via_executor_removes_added_column_and_emits(self, ctx):
        """AnalysisCommand itself never reaches the undo stack; the pushed
        ApplyAnalysisResultCommand is what CommandExecutor.undo() acts on."""
        app_context, _, dataset, event_bus = ctx
        executor: CommandExecutor = app_context.get_command_executor()
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        assert executor.execute_command(command) is True
        assert isinstance(executor.undo_stack[-1], ApplyAnalysisResultCommand)

        assert executor.undo() is True
        assert "dydx" not in dataset.data.columns
        assert _emitted(event_bus, DatasetOperationEvents.DATASET_COLUMN_REMOVED)

    def test_arc_length_line_on_plot(self, ctx):
        app_context, _, dataset, _ = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "arc_length", "x_column": "x", "y_column": "y",
            "new_column_name": "arc",
        })
        assert command.execute() is CommandResult.SUCCESS
        arc = dataset.data["arc"]
        assert arc.iloc[0] == pytest.approx(0.0)
        assert (arc.diff().dropna() >= 0).all()

    def test_same_column_as_both_x_and_y_still_works(self, ctx):
        """Regression test: the background task's dataframe slice must dedupe
        x_column/y_column before selecting, or `df[[x, y]]` (with x == y)
        collapses to a single-column DataFrame and `_execute_analysis`'s
        `df[self.x_column]` access returns a DataFrame instead of a Series,
        breaking the analysis engine call."""
        app_context, _, dataset, _ = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "x",
            "new_column_name": "dxdx",
        })
        assert command.execute() is CommandResult.SUCCESS
        # d(x)/d(x) == 1 everywhere.
        assert dataset.data["dxdx"].iloc[5] == pytest.approx(1.0)


class TestAnalysisCommandConcurrentMutation:
    def test_reruns_column_existence_check_after_async_computation_completes(self, ctx):
        """Regression test (PR review): column_existed_before/original_data
        must be re-derived from the dataset's *current* state once the
        background computation completes, not trusted from the stale
        snapshot taken at dispatch time -- otherwise a column added by
        another command while this one's computation was running gets
        silently dropped (instead of restored) when this command is undone."""
        app_context, _, dataset, _ = ctx
        task_scheduler = Mock()
        app_context.get_task_scheduler.return_value = task_scheduler

        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        assert command.execute() is CommandResult.SUCCESS
        assert command.column_existed_before is False  # snapshot at dispatch time
        _, kwargs = task_scheduler.run_task.call_args

        # Simulate another command adding "dydx" to the dataset while this
        # command's computation is still "running" in the background.
        concurrent_df = dataset.data.copy()
        concurrent_df["dydx"] = 999.0
        dataset.set_data(concurrent_df)

        # Now let the (previously un-run) task actually compute, and deliver
        # its result the way TaskScheduler would.
        outcome = kwargs["task"](lambda *_: None, **kwargs["task_arguments"])
        kwargs["on_result"](outcome)

        # The applied result overwrote the concurrently-added column...
        assert dataset.data["dydx"].iloc[0] != 999.0

        # ...and undo restores that concurrent value instead of deleting the
        # column outright, proving column_existed_before was re-derived as
        # True at apply time rather than trusting the stale `False` snapshot.
        executor = app_context.get_command_executor()
        assert executor.undo() is True
        assert dataset.data["dydx"].iloc[0] == pytest.approx(999.0)

    def test_project_changed_while_running_discards_the_result(self, ctx):
        """Regression test (PR review): re-resolving the dataset from
        whichever project happens to be current when the background task
        finishes is wrong if a different project (persisting a dataset with
        the same id) was loaded in the meantime -- the result would be
        silently applied to that other project's dataset instead."""
        app_context, _, dataset, _ = ctx
        task_scheduler = Mock()
        task_scheduler.run_task.side_effect = lambda **kwargs: captured.update(kwargs)
        app_context.get_task_scheduler.return_value = task_scheduler
        captured = {}

        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        assert command.execute() is CommandResult.SUCCESS  # dispatched only

        # Simulate the user closing this project and opening another one
        # while the computation is still "running" in the background.
        other_project = Project(name="Other")
        app_context.get_app_state.return_value.current_project = other_project

        outcome = captured["task"](lambda *_: None, **captured["task_arguments"])
        captured["on_result"](outcome)

        assert "dydx" not in dataset.data.columns
        app_context.get_ui_controller.return_value.show_warning_message.assert_called_once()


class TestAnalysisCommandGuards:
    def test_execute_fails_fast_when_already_running(self, ctx):
        app_context, _, _, _ = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        command._is_running = True

        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_info_message.assert_called_once()

    def test_execute_dispatches_via_task_scheduler(self, ctx):
        app_context, _, _, _ = ctx
        task_scheduler = Mock()
        app_context.get_task_scheduler.return_value = task_scheduler

        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        assert command.execute() is CommandResult.SUCCESS
        task_scheduler.run_task.assert_called_once()
        _, kwargs = task_scheduler.run_task.call_args
        assert kwargs["task"] == command._compute_analysis_task
        assert "df" in kwargs["task_arguments"]


def test_cleanup_is_a_documented_noop():
    """AnalysisCommand never occupies an undo slot, so CommandExecutor never
    calls cleanup() on it; kept as a no-op to satisfy the Command interface."""
    app_context = Mock(spec=AppContext)
    command = AnalysisCommand(app_context, "ds-1", {
        "analysis_type": "derivative", "x_column": "x", "y_column": "y",
        "new_column_name": "dydx",
    })
    command.cleanup()  # must not raise


class TestApplyAnalysisResultCommand:
    def test_cleanup_releases_the_original_data_snapshot(self):
        app_context = Mock(spec=AppContext)
        app_context.get_ui_controller.return_value = Mock()

        command = ApplyAnalysisResultCommand(
            app_context, "ds-1", "dydx", pd.Series([1.0, 2.0]), False, None,
        )
        command.original_data = pd.Series([1, 2, 3])

        command.cleanup()

        assert command.original_data is None

    def test_positional_assignment_does_not_materialize_a_python_list(self, ctx, monkeypatch):
        """Regression test (PR review): the positional-assignment branch
        (result doesn't align to existing rows, e.g. interpolation resamples
        to a new grid) used to coerce the result through `list(...)` before
        assignment -- slow and memory-heavy for a large result. It must
        assign directly from the array/Series instead."""
        app_context, _, dataset, _ = ctx
        result = np.array([100.0, 200.0, 300.0])  # shorter than the dataset's 11 rows

        def _forbid_listing_the_result(arg):
            assert arg is not result, "must not materialize the result through list(...)"
            return list(arg)

        monkeypatch.setattr(
            "pandaplot.commands.project.dataset.apply_analysis_result_command.list",
            _forbid_listing_the_result,
            raising=False,
        )

        command = ApplyAnalysisResultCommand(
            app_context, "ds-1", "resampled", result, False, None,
        )
        assert command.execute() is CommandResult.SUCCESS

        col = dataset.data["resampled"]
        assert list(col.iloc[:3]) == [100.0, 200.0, 300.0]

    def test_execute_fails_when_dataset_missing(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        app_state.has_project = False
        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = Mock()

        command = ApplyAnalysisResultCommand(
            app_context, "missing-ds", "dydx", pd.Series([1.0, 2.0]), False, None,
        )
        assert command.execute() is CommandResult.FAILURE
