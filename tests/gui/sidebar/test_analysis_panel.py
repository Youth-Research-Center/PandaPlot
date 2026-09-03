"""Tests for AnalysisPanel segment index -> (x, y) preview labels, and for
apply_analysis()'s async dispatch wiring (busy spinner, button state,
success/failure/sync-dispatch-failure), mirroring the pattern established for
FitPanel's PerformFitCommand dispatch in test_fit_panel.py."""
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.commands.base_command import CommandResult
from pandaplot.gui.components.sidebar.analysis.analysis_panel import AnalysisPanel
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


@pytest.fixture
def dataset():
    t = np.linspace(0.0, 10.0, 101)
    return Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "sq": t ** 2}))


@pytest.fixture
def panel(app_context, dataset):
    panel = AnalysisPanel(app_context)
    panel.current_dataset = dataset
    panel.current_dataset_id = "ds-1"
    panel.update_column_choices()
    return panel


class TestAnalysisPanelRangeLabels:
    def test_labels_show_placeholder_without_dataset(self, app_context):
        panel = AnalysisPanel(app_context)

        assert panel.start_value_label.text() == "–"
        assert panel.end_value_label.text() == "–"

    def test_end_row_defaults_to_the_last_row(self, panel):
        assert panel.start_index.minimum() == 1
        assert panel.end_index.minimum() == 1
        assert panel.end_index.value() == 101
        assert panel.end_value_label.text() == "x=10, y=100"

    def test_start_label_updates_on_row_number_change(self, panel):
        # Row 11 (1-based) is the 0-based index 10.
        panel.start_index.setValue(11)

        assert panel.start_value_label.text() == "x=1, y=1"

    def test_end_row_shrinks_the_segment_when_decreased(self, panel):
        panel.end_index.setValue(panel.end_index.value() - 1)

        assert panel.end_value_label.text() == "x=9.9, y=98.01"

    def test_get_analysis_config_converts_row_numbers_to_engine_indices(self, panel):
        panel.start_index.setValue(1)
        panel.end_index.setValue(50)
        panel.result_column_name.setText("result")

        params = panel.get_analysis_config()["parameters"]
        assert params["start_index"] == 0
        assert params["end_index"] == 50


def _ready_to_apply(panel, *, dispatch_return=True):
    """Set panel up so validate_inputs() passes, and capture the
    AnalysisCommand dispatched via execute_command (without actually
    executing it), returning `dispatch_return` from execute_command."""
    panel.result_column_name.setText("result_col")

    executed = {}

    def _capture_execute(command):
        executed["command"] = command
        return dispatch_return

    panel.app_context.get_command_executor.return_value.execute_command = _capture_execute
    return executed


class TestApplyAnalysisAsyncDispatch:
    def test_success_path_populates_preview_and_stops_spinner(self, panel):
        executed = _ready_to_apply(panel)

        panel.apply_analysis()

        command = executed["command"]
        assert panel.busy_spinner.is_running is True
        assert panel.apply_btn.isEnabled() is False

        command.on_complete(CommandResult.SUCCESS)

        assert panel.busy_spinner.is_running is False
        assert panel.apply_btn.isEnabled() is True
        assert "successfully" in panel.preview_text.toPlainText()
        assert "result_col" in panel.preview_text.toPlainText()

    def test_success_path_clears_the_pending_command_reference(self, panel):
        """Regression test (PR review): unlike FitPanel's/SignalPanel's
        equivalent fields, _pending_analysis_command was never reset after
        completion, keeping a stale strong reference (holding the full
        Dataset) alive on the panel indefinitely."""
        executed = _ready_to_apply(panel)

        panel.apply_analysis()
        assert panel._pending_analysis_command is executed["command"]

        executed["command"].on_complete(CommandResult.SUCCESS)

        assert panel._pending_analysis_command is None

    def test_on_complete_exception_is_shown_as_an_error_not_swallowed(self, panel):
        """Regression test (PR review): the outer try/except in
        apply_analysis() only covers the synchronous dispatch -- it does not
        run again when the async on_complete closure is invoked later from a
        Qt signal callback, so publish_event()/preview_text updates there
        need their own error handling to avoid silently swallowing a bug."""
        executed = _ready_to_apply(panel)
        panel.publish_event = Mock(side_effect=RuntimeError("boom"))

        panel.apply_analysis()
        executed["command"].on_complete(CommandResult.SUCCESS)

        assert panel.busy_spinner.is_running is False
        assert panel.apply_btn.isEnabled() is True
        assert panel._pending_analysis_command is None
        assert "boom" in panel.preview_text.toPlainText()

    def test_failure_path_shows_error_and_stops_spinner(self, panel):
        executed = _ready_to_apply(panel)

        panel.apply_analysis()

        command = executed["command"]
        command.on_complete(CommandResult.FAILURE)

        assert panel.busy_spinner.is_running is False
        assert panel.apply_btn.isEnabled() is True
        assert "failed" in panel.preview_text.toPlainText()

    def test_sync_dispatch_failure_stops_spinner_without_on_complete(self, panel):
        """When execute_command() returns False (e.g. an analysis already in
        progress), on_complete never fires -- apply_analysis() itself must
        undo the spinner/button state it set before dispatching."""
        executed = _ready_to_apply(panel, dispatch_return=False)

        panel.apply_analysis()

        assert "command" in executed  # dispatch was attempted
        assert panel.busy_spinner.is_running is False
        assert panel.apply_btn.isEnabled() is True
        assert "failed" in panel.preview_text.toPlainText()
