"""Tests for SignalPanel's async dispatch wiring: run_analysis()'s two-argument
on_complete(result, error) preview path and add_results_to_project()'s
one-argument on_complete(CommandResult) commit path. Mirrors the
success/failure/sync-dispatch-failure pattern established for FitPanel's
PerformFitCommand dispatch in test_fit_panel.py.

Both panel methods are driven with a fake command returned from a
monkeypatched _build_command(), so these tests exercise only the panel's own
busy-spinner/button/text wiring around the dispatch -- SignalAnalysisCommand's
own behavior is covered separately in
tests/commands/project/dataset/test_signal_analysis_command.py.
"""
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.commands.base_command import CommandResult
from pandaplot.gui.components.sidebar.signal.signal_panel import SignalPanel
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    return ctx


def _build_panel_with_column(app_context) -> SignalPanel:
    """Build a SignalPanel with a dataset loaded and a numeric signal column
    selected, so _build_command() (and thus run_analysis()/
    add_results_to_project()) doesn't bail out early with `None`."""
    df = pd.DataFrame({"signal": np.sin(np.linspace(0.0, 10.0, 50))})
    dataset = Dataset(id="ds-1", name="dataset", data=df)

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = SignalPanel(app_context)
    panel.app_context.get_app_state.return_value.current_project = project
    panel.on_tab_changed({"tab_type": "dataset", "tab_id": dataset.id})

    assert panel.column_combo.count() > 0  # sanity check: column got picked up
    return panel


def _fake_result():
    result = Mock()
    result.analysis_name = "FFT"
    result.data = pd.DataFrame({"frequency": [1.0, 2.0], "magnitude": [0.1, 0.2]})
    result.metadata = {}
    return result


class TestRunAnalysisAsyncDispatch:
    def test_success_path_populates_results_and_stops_spinner(self, app_context):
        panel = _build_panel_with_column(app_context)

        captured = {}
        fake_command = Mock()
        fake_command.run_analysis_async = lambda on_complete: captured.update(on_complete=on_complete)
        panel._build_command = lambda: fake_command

        panel.run_analysis()

        assert panel.busy_spinner.is_running is True
        assert panel.run_btn.isEnabled() is False
        assert panel.add_btn.isEnabled() is False

        result = _fake_result()
        captured["on_complete"](result, None)

        assert panel.busy_spinner.is_running is False
        assert panel.run_btn.isEnabled() is True
        assert panel.add_btn.isEnabled() is True
        assert panel.last_result is result
        assert "FFT" in panel.results_text.toPlainText()

    def test_format_result_exception_is_shown_as_an_error_not_swallowed(self, app_context):
        """Regression test (PR review): the old synchronous run_analysis()
        wrapped result-formatting in try/except so a formatting bug surfaced
        as a visible error. The async on_complete callback must keep that
        guarantee instead of letting an exception raised inside a Qt-signal
        callback vanish (Qt prints it to stderr, not to the user)."""
        panel = _build_panel_with_column(app_context)

        captured = {}
        fake_command = Mock()
        fake_command.run_analysis_async = lambda on_complete: captured.update(on_complete=on_complete)
        panel._build_command = lambda: fake_command

        panel.run_analysis()

        broken_result = Mock()
        broken_result.analysis_name = "FFT"
        # _format_result's first step is len(result.data); a plain object()
        # has no __len__, so this raises TypeError, simulating a malformed
        # result reaching the formatting step.
        broken_result.data = object()
        captured["on_complete"](broken_result, None)

        assert panel.busy_spinner.is_running is False
        assert panel.run_btn.isEnabled() is True
        assert panel.add_btn.isEnabled() is False
        assert panel.last_result is None
        assert "Analysis failed" in panel.results_text.toPlainText()

    def test_discards_stale_result_after_dataset_switch(self, app_context):
        """Regression test (PR review): tab/dataset navigation stays enabled
        while a preview computes in the background. If the user switches to
        a different dataset before the result comes back, displaying it
        would silently overwrite whatever the panel now shows for the new
        dataset."""
        panel = _build_panel_with_column(app_context)

        captured = {}
        fake_command = Mock()
        fake_command.run_analysis_async = lambda on_complete: captured.update(on_complete=on_complete)
        panel._build_command = lambda: fake_command

        panel.run_analysis()

        # Simulate switching to a different dataset while the preview is
        # still "running" in the background.
        panel.current_dataset_id = "ds-2"

        captured["on_complete"](_fake_result(), None)

        # The stale result must not have been installed over the new context.
        assert panel.last_result is None
        assert panel.add_btn.isEnabled() is False
        assert "FFT" not in panel.results_text.toPlainText()
        # But the panel isn't stuck busy either -- the preview did finish,
        # just for a dataset that's no longer selected.
        assert panel.busy_spinner.is_running is False
        assert panel.run_btn.isEnabled() is True

    def test_failure_path_shows_error_and_stops_spinner(self, app_context):
        panel = _build_panel_with_column(app_context)

        captured = {}
        fake_command = Mock()
        fake_command.run_analysis_async = lambda on_complete: captured.update(on_complete=on_complete)
        panel._build_command = lambda: fake_command

        panel.run_analysis()
        captured["on_complete"](None, "Analysis blew up")

        assert panel.busy_spinner.is_running is False
        assert panel.run_btn.isEnabled() is True
        assert panel.add_btn.isEnabled() is False
        assert panel.last_result is None
        assert "Analysis blew up" in panel.results_text.toPlainText()

    def test_sync_dispatch_failure_stops_spinner_without_leftover_busy_state(self, app_context):
        """run_analysis_async() can call on_complete synchronously (e.g. the
        real SignalAnalysisCommand does this when the source dataset or
        column is missing, before ever touching the TaskScheduler). The
        panel's on_complete closure must leave no stale busy/disabled state
        behind even though it fired inline instead of from a background
        thread."""
        panel = _build_panel_with_column(app_context)

        fake_command = Mock()
        fake_command.run_analysis_async = lambda on_complete: on_complete(None, "Column not found: signal")
        panel._build_command = lambda: fake_command

        panel.run_analysis()

        assert panel.busy_spinner.is_running is False
        assert panel.run_btn.isEnabled() is True
        assert panel.add_btn.isEnabled() is False
        assert panel.last_result is None
        assert "Column not found: signal" in panel.results_text.toPlainText()


class TestAddResultsToProjectAsyncDispatch:
    def _ready(self, app_context, *, dispatch_return=True):
        panel = _build_panel_with_column(app_context)

        fake_command = Mock()
        fake_command.result = Mock()

        executed = {}

        def _capture_execute(command):
            executed["command"] = command
            return dispatch_return

        panel.app_context.get_command_executor.return_value.execute_command = _capture_execute
        panel._build_command = lambda: fake_command

        return panel, fake_command, executed

    def test_success_path_appends_confirmation_and_stops_spinner(self, app_context):
        panel, fake_command, executed = self._ready(app_context)

        panel.add_results_to_project()

        assert executed["command"] is fake_command
        assert panel.busy_spinner.is_running is True
        assert panel.add_btn.isEnabled() is False

        fake_command.on_complete(CommandResult.SUCCESS)

        assert panel.busy_spinner.is_running is False
        assert panel.last_result is fake_command.result
        assert "added to project" in panel.results_text.toPlainText().lower()
        # Not re-enabled on success -- matches add_results_to_project()'s
        # real behavior of only re-enabling the button to let the user retry
        # after a failure.
        assert panel.add_btn.isEnabled() is False

    def test_discards_stale_result_display_after_dataset_switch(self, app_context):
        """Regression test (PR review): the same stale-completion problem as
        run_analysis()'s -- the commit itself already happened for real
        (the dataset was created regardless), but *displaying* that outcome
        must not overwrite whatever the panel now shows if the user
        switched datasets while the commit was in flight."""
        panel, fake_command, executed = self._ready(app_context)

        panel.add_results_to_project()
        panel.current_dataset_id = "ds-2"

        fake_command.on_complete(CommandResult.SUCCESS)

        assert panel.last_result is None
        assert "added to project" not in panel.results_text.toPlainText().lower()
        assert panel.busy_spinner.is_running is False
        assert panel.run_btn.isEnabled() is True

    def test_failure_path_reenables_add_button_and_stops_spinner(self, app_context):
        panel, fake_command, executed = self._ready(app_context)

        panel.add_results_to_project()
        fake_command.on_complete(CommandResult.FAILURE)

        assert panel.busy_spinner.is_running is False
        assert panel.add_btn.isEnabled() is True

    def test_sync_dispatch_failure_stops_spinner_without_on_complete(self, app_context):
        """When execute_command() returns False (e.g. a signal analysis
        already in progress), on_complete never fires --
        add_results_to_project() itself must undo the spinner/button state
        it set before dispatching."""
        panel, fake_command, executed = self._ready(app_context, dispatch_return=False)

        panel.add_results_to_project()

        assert executed["command"] is fake_command  # dispatch was attempted
        assert panel.busy_spinner.is_running is False
        assert panel.add_btn.isEnabled() is True


class TestRunAndAddMutualExclusion:
    """Regression tests (PR review): Run and Add to Project share one busy
    spinner and one _pending_command slot. Letting both be in flight at once
    lets whichever finishes first stop the shared spinner and clear the
    other's still-active reference while its work is still running."""

    def test_add_is_a_no_op_while_run_is_in_flight(self, app_context):
        panel = _build_panel_with_column(app_context)

        run_captured = {}
        run_command = Mock()
        run_command.run_analysis_async = lambda on_complete: run_captured.update(on_complete=on_complete)
        panel._build_command = lambda: run_command
        panel.run_analysis()
        assert panel._pending_command is run_command

        add_attempted = {}

        def _build_add_command():
            add_attempted["built"] = True
            return Mock()

        panel._build_command = _build_add_command
        panel.add_results_to_project()

        assert "built" not in add_attempted  # add_results_to_project() bailed out immediately
        assert panel._pending_command is run_command  # Run's reference untouched

    def test_run_is_a_no_op_while_add_is_in_flight(self, app_context):
        panel = _build_panel_with_column(app_context)

        add_command = Mock()
        add_command.result = Mock()
        panel.app_context.get_command_executor.return_value.execute_command = lambda command: True
        panel._build_command = lambda: add_command
        panel.add_results_to_project()
        assert panel._pending_command is add_command

        run_attempted = {}

        def _build_run_command():
            run_attempted["built"] = True
            return Mock()

        panel._build_command = _build_run_command
        panel.run_analysis()

        assert "built" not in run_attempted  # run_analysis() bailed out immediately
        assert panel._pending_command is add_command  # Add's reference untouched

    def test_add_disables_run_too_while_committing(self, app_context):
        panel = _build_panel_with_column(app_context)

        add_command = Mock()
        add_command.result = Mock()
        panel.app_context.get_command_executor.return_value.execute_command = lambda command: True
        panel._build_command = lambda: add_command

        panel.add_results_to_project()

        assert panel.run_btn.isEnabled() is False
        assert panel.add_btn.isEnabled() is False

        add_command.on_complete(CommandResult.SUCCESS)

        assert panel.run_btn.isEnabled() is True
