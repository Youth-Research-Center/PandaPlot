"""Tests for ProjectPanelCommandManager.create_chart_from_dataset."""
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from pandaplot.commands.project.dataset.analyze_measurements_command import AnalyzeMeasurementsCommand
from pandaplot.gui.components.sidebar.project.project_command_manager import (
    ProjectPanelCommandManager,
)
from pandaplot.models.project import Project
from pandaplot.models.project.items import Dataset


def _fake_selected_item(dataset_obj):
    item = Mock()
    item.data.return_value = {"type": "dataset", "id": dataset_obj.id, "data": dataset_obj}
    return item


def _manager(app_context, dataset_obj):
    manager = ProjectPanelCommandManager.__new__(ProjectPanelCommandManager)
    manager.logger = Mock()
    manager.app_context = app_context
    manager.get_current_item = Mock(return_value=_fake_selected_item(dataset_obj))
    return manager


def _dataset_obj():
    dataset_obj = Mock()
    dataset_obj.id = "ds-1"
    dataset_obj.name = "Sales"
    dataset_obj.parent_id = "folder-1"
    return dataset_obj


def _app_context_with_tab(dataset_tab):
    """An app context whose TabContainer returns `dataset_tab` for any id."""
    tab_container = Mock()
    tab_container.get_tab_widget.return_value = dataset_tab
    app_context = Mock()
    app_context.get_manager.return_value = tab_container
    return app_context


@patch("pandaplot.gui.components.sidebar.project.project_command_manager.CreateChartFromWizardCommand")
def test_create_chart_from_dataset_preselects_columns_when_the_tab_is_open(mock_command_cls):
    dataset_tab = Mock()
    dataset_tab.table_view.get_selected_column_ids.return_value = ["col-date", "col-rev"]
    app_context = _app_context_with_tab(dataset_tab)
    dataset_obj = _dataset_obj()

    _manager(app_context, dataset_obj).create_chart_from_dataset()

    mock_command_cls.assert_called_once_with(
        app_context,
        dataset_id="ds-1",
        preselected_column_ids=["col-date", "col-rev"],
    )
    app_context.get_command_executor.return_value.execute_command.assert_called_once_with(
        mock_command_cls.return_value
    )


@patch("pandaplot.gui.components.sidebar.project.project_command_manager.CreateChartFromWizardCommand")
def test_create_chart_from_dataset_preselects_nothing_when_the_tab_is_not_open(mock_command_cls):
    # The dataset tab commonly is not open when charting from the project tree.
    app_context = _app_context_with_tab(None)
    dataset_obj = _dataset_obj()

    _manager(app_context, dataset_obj).create_chart_from_dataset()

    mock_command_cls.assert_called_once_with(
        app_context, dataset_id="ds-1", preselected_column_ids=[]
    )


@pytest.mark.parametrize("create_chart", [False, True])
def test_measurement_analysis_can_continue_to_chart_wizard(create_chart):
    project = Project("P")
    dataset = Dataset(id="ds-1", name="Experiment", data=pd.DataFrame({"x": [1], "y": [2]}))
    project.add_item(dataset)

    app_context = Mock()
    app_context.get_ui_controller.return_value = Mock()
    executor = app_context.get_command_executor.return_value

    def _execute(command):
        if isinstance(command, AnalyzeMeasurementsCommand):
            command.result_dataset_id = "summary-1"
        return True

    executor.execute_command.side_effect = _execute
    manager = ProjectPanelCommandManager.__new__(ProjectPanelCommandManager)
    manager.app_context = app_context
    manager.app_state = Mock()
    manager.app_state.current_project = project
    manager.get_selected_item_info = Mock(return_value={
        "type": "dataset",
        "id": dataset.id,
    })
    manager.parent_widget = None

    dialog = Mock()
    dialog.exec.return_value = 1
    dialog.selected_roles.return_value = {}
    dialog.selected_measurement_groups.return_value = {}
    dialog.result_name.return_value = "Summary"
    dialog.plot_requested.return_value = create_chart

    with (
        patch(
            "pandaplot.gui.dialogs.measurement_analysis_wizard.MeasurementAnalysisWizard",
            return_value=dialog,
        ),
        patch(
            "pandaplot.gui.components.sidebar.project.project_command_manager.CreateChartFromWizardCommand"
        ) as chart_command,
    ):
        manager.analyze_measurements()

    if create_chart:
        chart_command.assert_called_once_with(app_context, dataset_id="summary-1")
        assert executor.execute_command.call_count == 2
        assert executor.execute_command.call_args_list[1].args[0] is chart_command.return_value
    else:
        chart_command.assert_not_called()
        assert executor.execute_command.call_count == 1
