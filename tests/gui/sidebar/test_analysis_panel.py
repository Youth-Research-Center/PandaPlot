"""Tests for AnalysisPanel segment index -> (x, y) preview labels, and for
apply_analysis()'s async dispatch wiring (busy spinner, button state,
success/failure/sync-dispatch-failure), mirroring the pattern established for
FitPanel's PerformFitCommand dispatch in test_fit_panel.py."""
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QLabel

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.components.common.status_message import StatusKind
from pandaplot.gui.components.sidebar.analysis.analysis_panel import AnalysisPanel
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppState
from pandaplot.models.state.app_context import AppContext
from tests.commands.project.conftest import SyncTaskScheduler
from tests.gui.icon_testing import ICON_TOKENS, assert_tinted, strongest_pixel


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.get_manager.return_value.get_design_tokens.return_value = {"font_size_group_title": 9, **ICON_TOKENS}
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


class TestAnalysisPanelParameters:
    def test_smoothing_config_only_includes_current_method_parameters(self, panel):
        panel.analysis_type_combo.setCurrentText("Smoothing")
        panel.smooth_method_combo.setCurrentText("Rolling Mean")

        params = panel.get_analysis_config()["parameters"]
        assert params == {"start_index": 0, "end_index": 101, "method": "rolling_mean", "window": 5}

        panel.smooth_method_combo.setCurrentText("LOWESS")
        params = panel.get_analysis_config()["parameters"]
        assert params == {"start_index": 0, "end_index": 101, "method": "lowess"}

        panel.smooth_method_combo.setCurrentText("Savitzky-Golay")
        params = panel.get_analysis_config()["parameters"]
        assert params == {
            "start_index": 0,
            "end_index": 101,
            "method": "savgol",
            "window_length": 11,
            "polynomial_order": 3,
        }


class TestAnalysisPanelInterpolation:
    """Interpolation is stored as a new dataset, not as a column (#576)."""

    def test_result_field_names_a_dataset_for_interpolation(self, panel):
        label = panel.result_layout.labelForField(panel.result_column_name)
        assert label.text() == "Result Column:"
        assert panel.result_column_name.placeholderText() == "Enter column name..."
        assert not panel.replace_existing.isHidden()

        panel.analysis_type_combo.setCurrentText("Interpolation")

        assert label.text() == "Result Dataset:"
        assert panel.result_column_name.placeholderText() == "Enter dataset name..."
        assert panel.replace_existing.isHidden()

        panel.analysis_type_combo.setCurrentText("Smoothing")

        assert label.text() == "Result Column:"
        assert panel.result_column_name.placeholderText() == "Enter column name..."
        assert not panel.replace_existing.isHidden()

    def test_parameters_explain_where_the_result_goes(self, panel):
        panel.analysis_type_combo.setCurrentText("Interpolation")

        texts = [label.text() for label in panel.parameters_group.findChildren(QLabel)]
        assert "The result is added as a new dataset with the new X values and the interpolated Y values." in texts

    def test_success_message_says_a_dataset_was_added(self, panel):
        panel.analysis_type_combo.setCurrentText("Interpolation")
        executed = _ready_to_apply(panel)

        panel.apply_analysis()
        executed["command"].on_complete(CommandResult.SUCCESS)

        assert panel.status_message.kind() is StatusKind.SUCCESS
        assert panel.status_message.message() == (
            "Analysis applied successfully!\nThe interpolated values were added to the project as a new dataset."
        )

    def test_default_settings_on_a_small_dataset_create_the_interpolated_dataset(self, app_context):
        """Acceptance criterion of #576: the default Points (100) is larger
        than the 20 rows, and Apply used to fail with a pandas ValueError."""
        project = Project(name="P")
        x = np.linspace(0.0, 19.0, 20)
        small = Dataset(id="ds-small", name="Small", data=pd.DataFrame({"x": x, "y": 2.0 * x}))
        project.add_item(small)
        app_state = Mock(spec=AppState)
        app_state.has_project = True
        app_state.current_project = project
        app_state.event_bus = Mock()
        app_context.get_app_state.return_value = app_state
        app_context.get_task_scheduler.return_value = SyncTaskScheduler()
        app_context.get_command_executor.return_value = CommandExecutor()
        panel = AnalysisPanel(app_context)
        panel.current_dataset = small
        panel.current_dataset_id = "ds-small"
        panel.update_column_choices()
        panel.analysis_type_combo.setCurrentText("Interpolation")
        assert panel.num_points_spin.value() == 100 > len(small.data)
        assert panel.result_column_name.text() == "y_interpolation"

        panel.apply_analysis()

        assert panel.status_message.kind() is StatusKind.SUCCESS
        (result,) = [item for item in project.get_all_items() if isinstance(item, Dataset) and item is not small]
        assert result.name == "y_interpolation"
        assert len(result.data) == 100
        np.testing.assert_allclose(result.data["y (interpolated)"], 2.0 * result.data["x"])
        assert list(small.data.columns) == ["x", "y"]
        app_context.get_ui_controller.return_value.show_error_message.assert_not_called()


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
        assert panel.status_message.kind() is StatusKind.SUCCESS
        assert panel.status_message.message() == "Analysis applied successfully!\nColumn 'result_col' added to dataset."
        assert panel.preview_text.toPlainText() == ""

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
        assert panel.status_message.kind() is StatusKind.ERROR
        assert panel.status_message.message() == "Error applying analysis: boom"

    def test_failure_path_shows_error_and_stops_spinner(self, panel):
        executed = _ready_to_apply(panel)

        panel.apply_analysis()

        command = executed["command"]
        command.on_complete(CommandResult.FAILURE)

        assert panel.busy_spinner.is_running is False
        assert panel.apply_btn.isEnabled() is True
        assert panel.status_message.kind() is StatusKind.ERROR
        assert panel.status_message.message() == "Command execution failed. Please check your inputs."

    def test_sync_dispatch_failure_stops_spinner_without_on_complete(self, panel):
        """When execute_command() returns False (e.g. an analysis already in
        progress), on_complete never fires -- apply_analysis() itself must
        undo the spinner/button state it set before dispatching."""
        executed = _ready_to_apply(panel, dispatch_return=False)

        panel.apply_analysis()

        assert "command" in executed  # dispatch was attempted
        assert panel.busy_spinner.is_running is False
        assert panel.apply_btn.isEnabled() is True
        assert panel.status_message.kind() is StatusKind.ERROR
        assert panel.status_message.message() == "Command execution failed. Please check your inputs."


class TestAnalysisPanelStatusMessage:
    def test_status_message_sits_directly_above_the_preview_text(self, panel):
        layout = panel.preview_text.parentWidget().layout()

        assert layout.indexOf(panel.status_message) == layout.indexOf(panel.preview_text) - 1
        assert panel.status_message.isHidden()

    @pytest.mark.parametrize(
        ("setup", "expected"),
        [
            (lambda p: setattr(p, "current_dataset", None), "No dataset selected."),
            (lambda p: setattr(p.current_dataset, "data", None), "Dataset data is not available."),
            (lambda p: p.result_column_name.clear(), "Please enter a result column name."),
        ],
    )
    def test_validation_failures_show_an_error_without_an_emoji(self, panel, setup, expected):
        panel.result_column_name.setText("result_col")
        panel.preview_text.setPlainText("stale preview")
        setup(panel)

        assert panel.validate_inputs() is False

        assert panel.status_message.kind() is StatusKind.ERROR
        assert panel.status_message.message() == expected
        assert panel.preview_text.toPlainText() == ""

    def test_apply_without_a_dataset_id_shows_an_error(self, panel):
        panel.result_column_name.setText("result_col")
        panel.current_dataset_id = None

        panel.apply_analysis()

        assert panel.status_message.kind() is StatusKind.ERROR
        assert panel.status_message.message() == "Failed to apply analysis. Please check your inputs."

    def test_a_successful_preview_replaces_an_earlier_status(self, panel):
        panel.result_column_name.clear()
        panel.apply_analysis()
        assert panel.status_message.kind() is StatusKind.ERROR
        panel.result_column_name.setText("result_col")

        panel.preview_analysis()

        assert panel.status_message.message() == ""
        assert "Analysis Preview" in panel.preview_text.toPlainText()

    def test_a_preview_without_a_result_shows_an_error_status(self, panel, monkeypatch):
        panel.result_column_name.setText("result_col")
        panel.preview_text.setPlainText("stale preview")
        monkeypatch.setattr(panel, "execute_analysis_preview", lambda *_args: None)

        panel.preview_analysis()

        assert panel.status_message.kind() is StatusKind.ERROR
        assert panel.status_message.message() == "Preview failed. Please check your parameters."
        assert panel.preview_text.toPlainText() == ""

    def test_a_preview_exception_shows_an_error_status(self, panel, monkeypatch):
        panel.result_column_name.setText("result_col")
        panel.preview_text.setPlainText("stale preview")

        def explode(*_args):
            raise ValueError("bad window")

        monkeypatch.setattr(panel, "execute_analysis_preview", explode)

        panel.preview_analysis()

        assert panel.status_message.kind() is StatusKind.ERROR
        assert panel.status_message.message() == "Preview error: bad window"
        assert panel.preview_text.toPlainText() == ""

    def test_clear_inputs_clears_the_status_message(self, panel):
        panel.result_column_name.clear()
        panel.apply_analysis()
        assert panel.status_message.kind() is StatusKind.ERROR

        panel.clear_inputs()

        assert panel.status_message.message() == ""
        assert panel.status_message.kind() is None

    def test_theme_change_retints_the_status_icon(self, panel, app_context):
        panel.result_column_name.clear()
        panel.apply_analysis()
        app_context.get_manager.return_value.get_design_tokens.return_value["status_danger"] = "#00AA00"

        panel._apply_theme()

        assert_tinted(strongest_pixel(panel.status_message.findChild(IconLabel).pixmap()), "#00AA00")
