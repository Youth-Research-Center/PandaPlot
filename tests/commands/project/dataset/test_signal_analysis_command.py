"""Tests for SignalAnalysisCommand: preview (run_analysis_async) and
commit (execute -> ApplySignalAnalysisResultCommand) paths."""

import logging
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.analysis import SignalAnalysisType
from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.project.dataset.apply_signal_analysis_result_command import (
    ApplySignalAnalysisResultCommand,
)
from pandaplot.commands.project.dataset.signal_analysis_command import SignalAnalysisCommand
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState
from tests.commands.project.conftest import SyncTaskScheduler


@pytest.fixture
def app_context_with_project():
    fs = 1000
    t = np.linspace(0, 1, fs, endpoint=False)
    signal = np.sin(2 * np.pi * 50 * t)

    project = Project(name="P")
    dataset = Dataset(id="ds-1", name="Signal Data", data=pd.DataFrame({"signal": signal}))
    project.add_item(dataset)

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()

    app_context.get_app_state.return_value = app_state
    app_context.get_task_scheduler.return_value = SyncTaskScheduler()
    app_context.get_command_executor.return_value = CommandExecutor()

    return app_context, project


class TestSignalAnalysisCommandCommitPath:
    def test_execute_adds_fft_results_dataset(self, app_context_with_project):
        app_context, project = app_context_with_project
        command = SignalAnalysisCommand(
            app_context, "ds-1", SignalAnalysisType.FFT, "signal", sampling_rate=1000,
        )
        assert command.execute() is CommandResult.SUCCESS

        results = project.find_item(command.result_dataset_id)
        assert results is not None
        assert "Frequency (Hz)" in results.data.columns
        assert "Amplitude" in results.data.columns

    def test_occupies_no_undo_slot(self, app_context_with_project):
        app_context, _ = app_context_with_project
        command = SignalAnalysisCommand(app_context, "ds-1", SignalAnalysisType.PEAKS, "signal")
        assert command.occupies_undo_slot() is False

    def test_undo_via_executor_removes_results_dataset(self, app_context_with_project):
        app_context, project = app_context_with_project
        executor: CommandExecutor = app_context.get_command_executor()
        command = SignalAnalysisCommand(app_context, "ds-1", SignalAnalysisType.PEAKS, "signal")

        assert executor.execute_command(command) is True
        assert isinstance(executor.undo_stack[-1], ApplySignalAnalysisResultCommand)

        new_id = command.result_dataset_id
        assert project.find_item(new_id) is not None

        assert executor.undo() is True
        assert project.find_item(new_id) is None

    def test_missing_column_fails_gracefully(self, app_context_with_project):
        app_context, _ = app_context_with_project
        command = SignalAnalysisCommand(
            app_context, "ds-1", SignalAnalysisType.FFT, "missing", sampling_rate=1000,
        )
        assert command.execute() is CommandResult.FAILURE
        assert command.result_dataset_id is None
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_execute_surfaces_no_project_loaded_to_the_user(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        app_state.has_project = False
        app_state.current_project = None
        app_context.get_app_state.return_value = app_state
        app_context.get_task_scheduler.return_value = SyncTaskScheduler()

        command = SignalAnalysisCommand(
            app_context, "ds-1", SignalAnalysisType.FFT, "signal", sampling_rate=1000,
        )
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_execute_fails_fast_when_already_running(self, app_context_with_project, caplog):
        app_context, _ = app_context_with_project
        command = SignalAnalysisCommand(app_context, "ds-1", SignalAnalysisType.FFT, "signal", sampling_rate=1000)
        command._is_running = True

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "already in progress" in caplog.text

    def test_on_complete_reports_success(self, app_context_with_project):
        app_context, _ = app_context_with_project
        outcomes = []
        command = SignalAnalysisCommand(
            app_context, "ds-1", SignalAnalysisType.FFT, "signal", sampling_rate=1000,
            on_complete=outcomes.append,
        )
        assert command.execute() is CommandResult.SUCCESS
        assert outcomes == [CommandResult.SUCCESS]

    def test_redo_reuses_the_same_dataset_id(self, app_context_with_project):
        """Regression test (PR review): redo() delegates to execute(), which
        used to mint a brand-new dataset id and object every time -- after
        undo, a redo would silently swap the dataset out from under anything
        that had recorded the original id (e.g. a chart series sourcing from
        it). The dataset must be built once and re-added as the same object
        on redo, mirroring ApplyFitCommand._create_report()."""
        app_context, project = app_context_with_project
        executor: CommandExecutor = app_context.get_command_executor()
        command = SignalAnalysisCommand(app_context, "ds-1", SignalAnalysisType.PEAKS, "signal")

        assert executor.execute_command(command) is True
        original_id = command.result_dataset_id

        assert executor.undo() is True
        assert project.find_item(original_id) is None

        assert executor.redo() is True
        assert command.result_dataset_id == original_id
        assert project.find_item(original_id) is not None

    def test_project_changed_while_running_discards_the_result(self, app_context_with_project):
        """Regression test (PR review): the apply step resolved
        app_state.current_project only once the background result came
        back, rather than validating it against the project the signal was
        actually read from -- switching projects mid-computation silently
        added the result to whichever project became current."""
        app_context, project = app_context_with_project
        # Replace the real (synchronous) scheduler with one that just
        # captures the dispatched task instead of running it, so we can
        # simulate a project switch before the "result" callback fires.
        captured = {}
        fake_scheduler = Mock()
        fake_scheduler.run_task.side_effect = lambda **kwargs: captured.update(kwargs)
        app_context.get_task_scheduler.return_value = fake_scheduler

        command = SignalAnalysisCommand(app_context, "ds-1", SignalAnalysisType.FFT, "signal", sampling_rate=1000)
        assert command.execute() is CommandResult.SUCCESS  # dispatched only

        # Simulate the user closing this project and opening another one
        # while the computation is still "running" in the background.
        app_context.get_app_state.return_value.current_project = Project(name="Other")

        outcome = captured["task"](lambda *_: None, **captured["task_arguments"])
        captured["on_result"](outcome)

        assert command.result_dataset_id is None
        app_context.get_ui_controller.return_value.show_warning_message.assert_called_once()
        # The original project never got the result either.
        assert all(not isinstance(item, Dataset) or item.id == "ds-1" for item in project.items_index.values())

    def test_cleanup_releases_the_result_dataset_id_and_result(self, app_context_with_project):
        app_context, _ = app_context_with_project
        command = SignalAnalysisCommand(app_context, "ds-1", SignalAnalysisType.FFT, "signal", sampling_rate=1000)
        assert command.execute() is CommandResult.SUCCESS
        assert command.result_dataset_id is not None
        assert command.result is not None

        command.cleanup()

        assert command.result_dataset_id is None
        assert command.result is None


class TestSignalAnalysisCommandPreviewPath:
    def test_run_analysis_async_reports_result(self, app_context_with_project):
        app_context, _ = app_context_with_project
        command = SignalAnalysisCommand(app_context, "ds-1", SignalAnalysisType.FFT, "signal", sampling_rate=1000)

        results = []
        errors = []
        command.run_analysis_async(lambda result, error: (results.append(result), errors.append(error)))

        assert errors == [None]
        assert results[0] is not None
        assert "Frequency (Hz)" in results[0].data.columns

    def test_run_analysis_async_reports_missing_column(self, app_context_with_project):
        app_context, _ = app_context_with_project
        command = SignalAnalysisCommand(app_context, "ds-1", SignalAnalysisType.FFT, "missing", sampling_rate=1000)

        results = []
        errors = []
        command.run_analysis_async(lambda result, error: (results.append(result), errors.append(error)))

        assert results == [None]
        assert "missing" in errors[0]

    def test_run_analysis_async_does_not_touch_the_project(self, app_context_with_project):
        app_context, project = app_context_with_project
        before = len(project.get_all_items())

        command = SignalAnalysisCommand(app_context, "ds-1", SignalAnalysisType.FFT, "signal", sampling_rate=1000)
        command.run_analysis_async(lambda result, error: None)

        assert len(project.get_all_items()) == before


def test_marks_project_modified_is_false(app_context_with_project):
    """Regression: execute() only dispatches the computation and returns
    SUCCESS before anything has actually mutated the project -- the
    dispatched computation may yet fail or be discarded (see
    _on_commit_computed). Flagging the project as modified here, before
    ApplySignalAnalysisResultCommand (the real mutation) ever runs, would
    leave a false "unsaved changes" state if the computation never
    actually applies."""
    app_context, _ = app_context_with_project
    command = SignalAnalysisCommand(app_context, "ds-1", SignalAnalysisType.FFT, "signal", sampling_rate=1000)
    assert command.marks_project_modified() is False


class TestSignalAnalysisCommandRealTaskScheduler:
    """Every other test in this suite (and every other converted command's
    tests) substitutes SyncTaskScheduler for TaskScheduler, which runs the
    task inline on the calling thread instead of via QThreadPool. That never
    exercises the assumption this whole feature branch depends on: that Qt
    actually delivers Worker's `result`/`error`/`finished` signals back on
    the GUI thread, which is what makes it safe for on_complete callbacks to
    touch widgets/event bus/CommandExecutor without their own locking. This
    test uses the real TaskScheduler (real QThreadPool background thread)
    and pytest-qt's qtbot.waitUntil to wait for the callback to actually
    fire, proving the whole pipeline works end to end -- not just that the
    command's own glue code is correct in isolation."""

    def test_run_analysis_async_via_real_task_scheduler_delivers_result_on_main_thread(
        self, qtbot, app_context_with_project
    ):
        import threading

        from pandaplot.services.qtasks.task_scheduler import TaskScheduler

        app_context, _ = app_context_with_project
        app_context.get_task_scheduler.return_value = TaskScheduler()

        command = SignalAnalysisCommand(
            app_context, "ds-1", SignalAnalysisType.FFT, "signal", sampling_rate=1000,
        )

        main_thread = threading.current_thread()
        outcome = {}

        def _on_complete(result, error):
            outcome["result"] = result
            outcome["error"] = error
            outcome["thread"] = threading.current_thread()

        command.run_analysis_async(_on_complete)

        # The task itself must actually run on a different thread -- if this
        # ever ran inline (e.g. a regression collapsing TaskScheduler back to
        # something synchronous), this test would still pass on the
        # thread-identity assertion below by accident, so also make sure we
        # genuinely waited for a background hop rather than the callback
        # already having fired synchronously.
        assert "thread" not in outcome

        qtbot.waitUntil(lambda: "thread" in outcome, timeout=5000)

        assert outcome["error"] is None
        assert outcome["result"] is not None
        assert "Frequency (Hz)" in outcome["result"].data.columns
        # Qt queues Worker's signals back to the thread that created the
        # worker (the GUI/main thread here) -- on_complete must be invoked
        # there, not on the background QThreadPool worker thread.
        assert outcome["thread"] is main_thread
