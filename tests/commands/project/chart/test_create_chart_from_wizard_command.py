"""Tests for CreateChartFromWizardCommand.

The wizard is opened non-blocking (`show()` + `finished` signal), so
`execute()` only opens it; the chart is built later in `_on_wizard_finished`.
These unit tests therefore drive that slot directly instead of relying on a
return value from `dialog.exec()`.
"""
import gc
import logging
from types import MethodType
from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.chart import CreateChartFromWizardCommand
from pandaplot.models.project.items import Dataset


@pytest.fixture
def app_context_with_project():
    dataset = Mock(spec=Dataset)
    dataset.id = "ds-1"
    dataset.name = "ds"
    dataset.parent_id = None
    dataset.data = None

    project = Mock()
    project.find_item.return_value = dataset
    project.get_all_items.return_value = [dataset]
    # Mirror both halves of Project's real behaviour (see
    # ItemCollection.add_item / ItemCollection.remove_item): `add_item` sets
    # the inserted item's own `.parent_id`, and `remove_item_by_id` clears it
    # back to `None`. Tracking inserted items here is what makes that
    # removal side effect possible without a static id->item mapping.
    inserted_items = {}

    def _add_item(item, parent_id=None):
        item.parent_id = parent_id
        inserted_items[item.id] = item

    def _remove_item_by_id(item_id):
        item = inserted_items.pop(item_id, None)
        if item is not None:
            item.parent_id = None

    project.add_item.side_effect = _add_item
    project.remove_item_by_id.side_effect = _remove_item_by_id

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    app_context.event_bus = Mock()
    app_context.get_command_executor.return_value.execute_command = Mock(return_value=True)
    return app_context, project


def _dataset(dataset_id, name, parent_id):
    dataset = Mock(spec=Dataset)
    dataset.id = dataset_id
    dataset.name = name
    dataset.parent_id = parent_id
    dataset.data = None
    dataset.column_name.return_value = None
    return dataset


def _fake_wizard(chart_type="line", *, is_empty=False, series_configs=None,
                  title="", x_label="", y_label="", subtitle="", show_legend=True, show_grid=True):
    """A stand-in for `ChartWizard` with a mockable `finished` signal."""
    wizard = Mock()
    wizard.finished = Mock()
    wizard.get_chart_type.return_value = chart_type
    wizard.is_empty.return_value = is_empty
    wizard.get_series_configs.return_value = series_configs or []
    wizard.get_title.return_value = title
    wizard.get_x_label.return_value = x_label
    wizard.get_y_label.return_value = y_label
    wizard.get_subtitle.return_value = subtitle
    wizard.get_show_legend.return_value = show_legend
    wizard.get_show_grid.return_value = show_grid
    return wizard


def _created_chart(app_context):
    """The Chart built by the wizard, extracted from the CreateChartCommand
    handed to execute_command() -- CreateChartFromWizardCommand no longer
    calls project.add_item() itself (see CreateChartCommand)."""
    execute_command_mock = app_context.get_command_executor.return_value.execute_command
    command = execute_command_mock.call_args[0][0]
    return command.chart


def _created_parent_id(app_context):
    execute_command_mock = app_context.get_command_executor.return_value.execute_command
    command = execute_command_mock.call_args[0][0]
    return command.parent_id


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_execute_shows_the_wizard_without_blocking(mock_wizard_cls, app_context_with_project):
    """`execute()` must `show()` the wizard, never `exec()` it.

    A blocking `exec()` loop is what made the pick-from-dataset modality
    handoff impossible (the wizard can't be hidden/re-shown without killing
    the loop), so this is a regression guard on the core fix.
    """
    app_context, _ = app_context_with_project
    wizard = _fake_wizard()
    mock_wizard_cls.return_value = wizard

    command = CreateChartFromWizardCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    wizard.show.assert_called_once_with()
    wizard.exec.assert_not_called()
    wizard.finished.connect.assert_called_once()
    # `exec()` made the wizard application-modal implicitly; `show()` does not,
    # so the command must ask for it explicitly.
    wizard.setModal.assert_called_once_with(True)  # noqa: FBT003 - mirrors Qt's positional-only setModal call


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_execute_sets_delete_on_close_so_the_dialog_isnt_leaked(mock_wizard_cls, app_context_with_project):
    """Qt does not delete a `.show()`'d top-level widget on close by default;
    without WA_DeleteOnClose the dialog (and, via its `finished` closure,
    this command) would survive indefinitely as a hidden top-level widget."""
    app_context, _ = app_context_with_project
    wizard = _fake_wizard()
    mock_wizard_cls.return_value = wizard

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS

    wizard.setAttribute.assert_called_once_with(Qt.WidgetAttribute.WA_DeleteOnClose)


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_wizard_is_constructed_with_the_current_project(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    mock_wizard_cls.return_value = _fake_wizard()

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS

    assert mock_wizard_cls.call_args.kwargs["project"] is project


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_execute_passes_the_default_chart_name_as_initial_title(mock_wizard_cls, app_context_with_project):
    app_context, _ = app_context_with_project
    mock_wizard_cls.return_value = _fake_wizard()

    command = CreateChartFromWizardCommand(app_context, dataset_id="ds-1")
    assert command.execute() is CommandResult.SUCCESS

    assert mock_wizard_cls.call_args.kwargs["initial_title"] == "Chart from ds"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_wizard_title_and_axis_labels_are_applied_to_the_chart(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    series_configs = [{
        "dataset_id": "ds-1", "x_column_id": "col-date", "y_column_id": "col-rev",
        "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True,
    }]
    wizard = _fake_wizard(chart_type="line", series_configs=series_configs,
                           title="My Chart", x_label="Date", y_label="Revenue")
    mock_wizard_cls.return_value = wizard

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    assert created_chart.name == "My Chart"
    assert created_chart.config["title"] == "My Chart"
    assert created_chart.config["x_label"] == "Date"
    assert created_chart.config["y_label"] == "Revenue"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_a_blank_title_from_the_wizard_does_not_blank_out_the_default_name(
        mock_wizard_cls, app_context_with_project):
    """An unedited (blank) title/label field must not overwrite the
    constructor-set default with an empty string.

    Unlike the empty-wizard path, this drives the non-empty path (`is_empty`
    stays `False`, the `_fake_wizard` default) so `set_labels(...)` is
    actually called with the wizard's blank `""` title/labels -- exercising
    the `or None` guards this test is named for.
    """
    app_context, project = app_context_with_project
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line")

    command = CreateChartFromWizardCommand(app_context, dataset_id="ds-1")
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    assert created_chart.name == "Chart from ds"
    assert created_chart.config["title"] == "Chart from ds"
    assert created_chart.config["x_label"] == ""
    assert created_chart.config["y_label"] == ""


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_subtitle_and_legend_and_grid_are_applied_to_the_chart(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    wizard = _fake_wizard(chart_type="line", subtitle="A closer look", show_legend=False, show_grid=False)
    mock_wizard_cls.return_value = wizard

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    assert created_chart.config["subtitle"] == "A closer look"
    assert created_chart.config["show_legend"] is False
    assert created_chart.config["show_grid_x"] is False
    assert created_chart.config["show_grid_y"] is False


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_empty_path_never_reads_subtitle_or_legend_or_grid(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    wizard = _fake_wizard(chart_type="line", is_empty=True)
    mock_wizard_cls.return_value = wizard

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    wizard.get_subtitle.assert_not_called()
    wizard.get_show_legend.assert_not_called()
    wizard.get_show_grid.assert_not_called()


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_empty_path_never_reads_the_wizards_labels(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    wizard = _fake_wizard(chart_type="line", is_empty=True)
    mock_wizard_cls.return_value = wizard

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    wizard.get_title.assert_not_called()
    wizard.get_x_label.assert_not_called()
    wizard.get_y_label.assert_not_called()
    created_chart = _created_chart(app_context)
    assert created_chart.name == "New Chart"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_finished_is_connected_to_a_closure_not_a_bound_method(mock_wizard_cls, app_context_with_project):
    """The connection must keep the command alive while the wizard is open.

    PySide gives bound-method connections weak-reference-like treatment for the
    receiver, so `connect(self._on_wizard_finished)` does *not* keep the command
    alive. Nothing else holds a lasting reference to it either -- the
    CommandExecutor's undo stack drops entries past `max_undo_levels` (10) --
    so with a bound method, 10 unrelated commands run while the wizard sits open
    would collect the command and silently break Finish. A lambda closure holds
    a real strong reference instead.
    """
    app_context, _ = app_context_with_project
    wizard = _fake_wizard()
    mock_wizard_cls.return_value = wizard

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS

    callback = wizard.finished.connect.call_args[0][0]
    assert not isinstance(callback, MethodType), (
        "`finished` must not be connected to a bound method -- PySide would then "
        "hold the command only weakly"
    )
    assert callback is not command._on_wizard_finished


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_the_connected_callback_still_works_after_the_command_is_dropped(
        mock_wizard_cls, app_context_with_project):
    """Maximum-fidelity version of the lifetime guard.

    Drop every local reference to the command, force a full collection, then
    fire the callable the command handed to `finished.connect`: it must still
    create the chart, proving the connection itself keeps the command alive.
    """
    app_context, project = app_context_with_project
    wizard = _fake_wizard(chart_type="line", is_empty=True)
    mock_wizard_cls.return_value = wizard

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    callback = wizard.finished.connect.call_args[0][0]

    del command
    gc.collect()

    callback(QDialog.DialogCode.Accepted)

    app_context.get_command_executor.return_value.execute_command.assert_called_once()
    assert _created_chart(app_context).chart_type == "line"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_the_connected_callback_uses_its_own_wizard(mock_wizard_cls, app_context_with_project):
    """A finishing wizard must build from *its* state, not `self._dialog`'s.

    Belt-and-braces against any future path that replaces `self._dialog` while
    an older wizard is still pending.
    """
    app_context, project = app_context_with_project
    first = _fake_wizard(chart_type="line", is_empty=True)
    mock_wizard_cls.return_value = first

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    first_callback = first.finished.connect.call_args[0][0]

    # Simulate `self._dialog` having been replaced by a newer wizard.
    command._dialog = _fake_wizard(chart_type="scatter", is_empty=True)

    first_callback(QDialog.DialogCode.Accepted)

    assert _created_chart(app_context).chart_type == "line"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_execute_succeeds_before_the_wizard_has_finished(mock_wizard_cls, app_context_with_project):
    """Opening the wizard is itself success, whatever the user does next."""
    app_context, project = app_context_with_project
    mock_wizard_cls.return_value = _fake_wizard()

    command = CreateChartFromWizardCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    app_context.get_command_executor.return_value.execute_command.assert_not_called()
    assert command.created_chart_id is None
    assert command.created_chart is None


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_wizard_command_does_not_occupy_an_undo_slot(mock_wizard_cls, app_context_with_project):
    app_context, _ = app_context_with_project
    mock_wizard_cls.return_value = _fake_wizard()

    command = CreateChartFromWizardCommand(app_context)

    assert command.occupies_undo_slot() is False


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_redo_does_not_reopen_the_wizard(mock_wizard_cls, app_context_with_project):
    """redo() must be unreachable via CommandExecutor (occupies_undo_slot() is
    False), but this asserts it directly: even called by hand, redo() must not
    reopen a second wizard."""
    app_context, _ = app_context_with_project
    mock_wizard_cls.return_value = _fake_wizard()

    command = CreateChartFromWizardCommand(app_context)
    command.execute()
    command.redo()

    assert mock_wizard_cls.call_count == 1


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_execute_fails_without_a_loaded_project(mock_wizard_cls, app_context_with_project, caplog):
    app_context, _ = app_context_with_project
    app_context.get_app_state.return_value.has_project = False
    app_context.get_ui_controller.return_value.show_action_or_cancel.return_value = False
    mock_wizard_cls.return_value = _fake_wizard()

    command = CreateChartFromWizardCommand(app_context)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    mock_wizard_cls.assert_not_called()
    assert "no project" in caplog.text.lower()
    app_context.get_ui_controller.return_value.show_action_or_cancel.assert_called_once()


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_execute_continues_after_the_user_creates_a_project(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    app_state = app_context.get_app_state.return_value
    app_state.has_project = False
    app_context.get_ui_controller.return_value.show_action_or_cancel.return_value = True

    def _execute_command(command):
        app_state.has_project = True
        app_state.current_project = project

    app_context.get_command_executor.return_value.execute_command.side_effect = _execute_command
    mock_wizard_cls.return_value = _fake_wizard()

    command = CreateChartFromWizardCommand(app_context)
    result = command.execute()

    assert result is CommandResult.SUCCESS
    mock_wizard_cls.assert_called_once()


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_cancelled_wizard_creates_nothing(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    mock_wizard_cls.return_value = _fake_wizard()

    command = CreateChartFromWizardCommand(app_context)

    # Opening the wizard succeeded even though the user then cancelled it.
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Rejected)

    app_context.get_command_executor.return_value.execute_command.assert_not_called()
    assert command.created_chart_id is None


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_empty_path_creates_a_line_chart_with_no_series(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", is_empty=True)

    command = CreateChartFromWizardCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    assert created_chart.chart_type == "line"
    assert created_chart.data_series == []


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_wizard_created_chart_gets_explicit_default_size(mock_wizard_cls, app_context_with_project):
    """Reported live: "when creating chart through wizard, the chart is
    too small (it didn't use app default size)." Root cause: charts with
    config["width_cm"]/["height_cm"] left as None fall through to
    ChartEditorWidget's auto-fit-to-viewport path, which races a brand
    new tab's not-yet-settled layout and can bake in an undersized
    result. Setting the app defaults explicitly at creation time skips
    that racy path entirely for wizard charts."""
    app_context, project = app_context_with_project
    # `app_context_with_project` gives `app_context` as a bare `Mock()`, which
    # auto-creates a truthy attribute chain for any `get_manager(...)` call
    # instead of the real `AppContext.get_manager`'s `KeyError` when no
    # `ConfigManager` is registered -- that would make the code under test
    # read a `Mock` as a "real" `chart_display.default_width_cm` and never
    # fall through to its own literal defaults. Simulate the unregistered
    # manager explicitly so this test exercises the same fallback path a
    # real, config-manager-less `AppContext` would take.
    app_context.get_manager.side_effect = KeyError("ConfigManager not found")
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", is_empty=True)

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    assert created_chart.config["width_cm"] == pytest.approx(20.0)
    assert created_chart.config["height_cm"] == pytest.approx(15.0)


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_series_configs_become_data_series(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    series_configs = [{
        "dataset_id": "ds-1",
        "x_column_id": "col-date",
        "y_column_id": "col-rev",
        "x_error_column_id": "",
        "y_error_column_id": "",
        "error_symmetric": True,
    }]
    mock_wizard_cls.return_value = _fake_wizard(chart_type="hist", series_configs=series_configs)

    command = CreateChartFromWizardCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    assert created_chart.chart_type == "hist"
    assert len(created_chart.data_series) == 1
    assert created_chart.data_series[0].dataset_id == "ds-1"
    assert created_chart.data_series[0].x_column_id == "col-date"
    assert created_chart.data_series[0].y_column_id == "col-rev"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_multiple_series_get_distinct_default_colors(mock_wizard_cls, app_context_with_project):
    """Regression test: every wizard-created series used to land on its
    style class's own single hardcoded default color (no color= kwarg
    was ever passed), so a multi-series chart came out of the wizard
    with every series visually indistinguishable."""
    app_context, project = app_context_with_project
    series_configs = [
        {
            "dataset_id": "ds-1", "x_column_id": "col-date", "y_column_id": f"col-{i}",
            "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True,
        }
        for i in range(3)
    ]
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", series_configs=series_configs)

    command = CreateChartFromWizardCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    colors = [series.style.color for series in created_chart.data_series]
    assert len(set(colors)) == len(colors), f"expected distinct colors, got {colors}"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_series_gets_a_default_label_from_dataset_and_y_column(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    dataset = project.find_item("ds-1")
    dataset.name = "Sales"
    dataset.column_name.return_value = "Revenue"
    series_configs = [{
        "dataset_id": "ds-1", "x_column_id": "col-date", "y_column_id": "col-rev",
        "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True,
    }]
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", series_configs=series_configs)

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    assert created_chart.data_series[0].label == "Sales:Revenue"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_series_label_falls_back_to_dataset_name_when_y_column_unresolved(
        mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    dataset = project.find_item("ds-1")
    dataset.name = "Sales"
    dataset.column_name.return_value = None
    series_configs = [{
        "dataset_id": "ds-1", "x_column_id": "", "y_column_id": "col-rev",
        "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True,
    }]
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", series_configs=series_configs)

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    assert created_chart.data_series[0].label == "Sales"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_chart_is_named_after_its_dataset_at_construction_time(mock_wizard_cls, app_context_with_project):
    """The name must be passed to `Chart(...)`, not patched on afterwards.

    `Chart.__init__` snapshots `config["title"] = self.name`, so a name set
    after construction leaves the rendered title permanently empty.
    """
    app_context, project = app_context_with_project
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", is_empty=True)

    command = CreateChartFromWizardCommand(app_context, dataset_id="ds-1")

    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    assert created_chart.name == "Chart from ds"
    assert created_chart.config["title"] == "Chart from ds"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_chart_without_an_originating_dataset_falls_back_to_new_chart(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", is_empty=True)

    command = CreateChartFromWizardCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    assert created_chart.name == "New Chart"
    assert created_chart.config["title"] == "New Chart"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_create_chart_command_failure_is_reported_and_resets_created_chart(
        mock_wizard_cls, app_context_with_project):
    """If CreateChartCommand.execute() fails internally, it returns False
    instead of raising -- the caller here must notice that and surface an
    error, not silently report success (see finding: chart-creation failure
    was previously swallowed)."""
    app_context, project = app_context_with_project
    app_context.get_command_executor.return_value.execute_command.return_value = False
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", is_empty=True)

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    assert command.created_chart is None
    assert command.created_chart_id is None
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_an_exception_is_reported_and_does_not_propagate(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    wizard = _fake_wizard(chart_type="line")
    wizard.get_series_configs.side_effect = KeyError("y_column_id")
    mock_wizard_cls.return_value = wizard

    command = CreateChartFromWizardCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)  # must not raise

    app_context.get_command_executor.return_value.execute_command.assert_not_called()
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_a_failure_to_open_the_wizard_is_reported(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    mock_wizard_cls.side_effect = RuntimeError("boom")

    command = CreateChartFromWizardCommand(app_context)

    assert command.execute() is CommandResult.FAILURE
    app_context.get_command_executor.return_value.execute_command.assert_not_called()
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_chart_goes_in_its_single_datasets_folder(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    ds1 = _dataset("ds-1", "Sales", "folder-1")
    project.find_item.side_effect = lambda did: {"ds-1": ds1}.get(did)
    series_configs = [{
        "dataset_id": "ds-1", "x_column_id": "", "y_column_id": "col-rev",
        "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True,
    }]
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", series_configs=series_configs)

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    assert _created_parent_id(app_context) == "folder-1"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_chart_goes_in_the_shared_folder_of_multiple_datasets(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    ds1 = _dataset("ds-1", "Sales", "folder-1")
    ds2 = _dataset("ds-2", "Costs", "folder-1")
    project.find_item.side_effect = lambda did: {"ds-1": ds1, "ds-2": ds2}.get(did)
    series_configs = [
        {"dataset_id": "ds-1", "x_column_id": "", "y_column_id": "col-rev",
         "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True},
        {"dataset_id": "ds-2", "x_column_id": "", "y_column_id": "col-cost",
         "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True},
    ]
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", series_configs=series_configs)

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    assert _created_parent_id(app_context) == "folder-1"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_chart_goes_to_root_when_datasets_are_in_different_folders(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    ds1 = _dataset("ds-1", "Sales", "folder-1")
    ds2 = _dataset("ds-2", "Costs", "folder-2")
    project.find_item.side_effect = lambda did: {"ds-1": ds1, "ds-2": ds2}.get(did)
    series_configs = [
        {"dataset_id": "ds-1", "x_column_id": "", "y_column_id": "col-rev",
         "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True},
        {"dataset_id": "ds-2", "x_column_id": "", "y_column_id": "col-cost",
         "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True},
    ]
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", series_configs=series_configs)

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    assert _created_parent_id(app_context) is None


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_empty_plot_uses_the_originating_datasets_folder(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    dataset = project.find_item("ds-1")
    dataset.parent_id = "folder-1"
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", is_empty=True)

    command = CreateChartFromWizardCommand(app_context, dataset_id="ds-1")
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    assert _created_parent_id(app_context) == "folder-1"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_empty_plot_with_no_originating_dataset_goes_to_root(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", is_empty=True)

    command = CreateChartFromWizardCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    assert _created_parent_id(app_context) is None


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_vector_series_config_passes_through_u_v_magnitude(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    series_configs = [{
        "dataset_id": "ds-1",
        "x_column_id": "col-x", "y_column_id": "col-y",
        "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True,
        "u_column_id": "col-u", "v_column_id": "col-v", "magnitude_column_id": "col-m",
    }]
    mock_wizard_cls.return_value = _fake_wizard(chart_type="vector", series_configs=series_configs)

    command = CreateChartFromWizardCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    assert created_chart.chart_type == "vector"
    series = created_chart.data_series[0]
    assert series.style.u_column_id == "col-u"
    assert series.style.v_column_id == "col-v"
    assert series.style.magnitude_column_id == "col-m"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_error_bar_series_config_passes_through_to_style(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    series_configs = [{
        "dataset_id": "ds-1",
        "x_column_id": "col-date", "y_column_id": "col-rev",
        "x_error_column_id": "col-xerr", "y_error_column_id": "col-yerr",
        "error_symmetric": False,
    }]
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", series_configs=series_configs)

    command = CreateChartFromWizardCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    series = created_chart.data_series[0]
    assert series.style.error_bars.x_error_column_id == "col-xerr"
    assert series.style.error_bars.y_error_column_id == "col-yerr"
    assert series.style.error_bars.error_symmetric is False


@pytest.mark.parametrize("chart_type", ["colormap", "heatmap"])
@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_colormap_and_heatmap_series_config_passes_through_z_column(
        mock_wizard_cls, app_context_with_project, chart_type):
    from pandaplot.models.chart.series_style import ColormapSeriesStyle, HeatmapSeriesStyle

    app_context, project = app_context_with_project
    series_configs = [{
        "dataset_id": "ds-1",
        "x_column_id": "col-x", "y_column_id": "col-y",
        "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True,
        "z_column_id": "col-z",
    }]
    mock_wizard_cls.return_value = _fake_wizard(chart_type=chart_type, series_configs=series_configs)

    command = CreateChartFromWizardCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    created_chart = _created_chart(app_context)
    assert created_chart.chart_type == chart_type
    series = created_chart.data_series[0]
    expected_style_cls = ColormapSeriesStyle if chart_type == "colormap" else HeatmapSeriesStyle
    assert isinstance(series.style, expected_style_cls)
    assert series.style.z_column_id == "col-z"


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_non_vector_series_config_leaves_u_v_magnitude_empty(mock_wizard_cls, app_context_with_project):
    app_context, project = app_context_with_project
    series_configs = [{
        "dataset_id": "ds-1", "x_column_id": "col-date", "y_column_id": "col-rev",
        "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True,
    }]
    mock_wizard_cls.return_value = _fake_wizard(chart_type="line", series_configs=series_configs)

    command = CreateChartFromWizardCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    command._on_wizard_finished(QDialog.DialogCode.Accepted)

    series = _created_chart(app_context).data_series[0]
    assert not hasattr(series.style, "u_column_id")
    assert not hasattr(series.style, "v_column_id")
    assert not hasattr(series.style, "magnitude_column_id")


@patch("pandaplot.gui.dialogs.chart.chart_wizard.ChartWizard")
def test_cleanup_does_not_raise(mock_wizard_cls, app_context_with_project):
    """This command never occupies an undo slot, so CommandExecutor never
    calls cleanup() on it -- this only guards the documented no-op."""
    app_context, _ = app_context_with_project
    mock_wizard_cls.return_value = _fake_wizard()

    command = CreateChartFromWizardCommand(app_context)
    command.execute()

    command.cleanup()  # must not raise
