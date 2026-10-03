"""Tests for launching measurement analysis from a dataset tab."""

from unittest.mock import Mock, patch

import pandas as pd
from PySide6.QtWidgets import QDialog

from pandaplot.commands.project.chart.create_chart_from_wizard_command import CreateChartFromWizardCommand
from pandaplot.commands.project.dataset.analyze_measurements_command import AnalyzeMeasurementsCommand
from pandaplot.gui.components.tabs.tab_container_command_manager import TabContainerCommandManager
from pandaplot.models.project import Project
from pandaplot.models.project.items import ColumnRole, Dataset
from pandaplot.models.state import AppContext, AppState


def _context():
    project = Project("P")
    dataset = Dataset(
        id="ds",
        name="Experiment",
        data=pd.DataFrame({"area": [1, 1], "Velocity1": [2.0, 4.0], "Velocity2": [6.0, 8.0]}),
    )
    project.add_item(dataset)

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    app_context.get_command_executor.return_value = Mock()
    return app_context, project, dataset


def test_accepted_wizard_dispatches_command_with_suggested_values():
    app_context, _project, dataset = _context()
    wizard = Mock()
    wizard.exec.return_value = QDialog.DialogCode.Accepted
    wizard.create_chart_after_creation.return_value = False
    wizard.selected_roles.return_value = {
        dataset.column_id("area"): ColumnRole.CONTROLLED,
        dataset.column_id("Velocity1"): ColumnRole.MEASURED,
        dataset.column_id("Velocity2"): ColumnRole.MEASURED,
    }
    wizard.selected_measurement_groups.return_value = {
        dataset.column_id("Velocity1"): "Velocity",
        dataset.column_id("Velocity2"): "Velocity",
    }
    wizard.result_name.return_value = "Summary"

    with patch(
        "pandaplot.gui.components.tabs.tab_container_command_manager.MeasurementAnalysisWizard",
        return_value=wizard,
    ):
        TabContainerCommandManager(app_context).analyze_measurements_for_dataset("ds")

    command = app_context.get_command_executor.return_value.execute_command.call_args.args[0]
    assert isinstance(command, AnalyzeMeasurementsCommand)
    assert command.source_dataset_id == "ds"
    assert command.roles[dataset.column_id("area")] is ColumnRole.CONTROLLED
    assert command.measurement_groups[dataset.column_id("Velocity1")] == "Velocity"
    assert command.result_name == "Summary"
    app_context.get_command_executor.return_value.execute_command.assert_called_once_with(command)


def test_accepted_wizard_can_continue_to_chart_wizard_from_result_dataset():
    app_context, project, dataset = _context()
    wizard = Mock()
    wizard.exec.return_value = QDialog.DialogCode.Accepted
    wizard.create_chart_after_creation.return_value = True
    wizard.selected_roles.return_value = {
        dataset.column_id("area"): ColumnRole.CONTROLLED,
        dataset.column_id("Velocity1"): ColumnRole.MEASURED,
        dataset.column_id("Velocity2"): ColumnRole.MEASURED,
    }
    wizard.selected_measurement_groups.return_value = {
        dataset.column_id("Velocity1"): "Velocity",
        dataset.column_id("Velocity2"): "Velocity",
    }
    wizard.result_name.return_value = "Summary"
    executor = app_context.get_command_executor.return_value

    def _execute(command):
        if isinstance(command, AnalyzeMeasurementsCommand):
            command.result_dataset_id = "summary-dataset"
            project.add_item(Dataset(
                id="summary-dataset",
                name="Summary",
                data=pd.DataFrame({"area": [1], "Mean": [5.0]}),
            ))
        return True

    executor.execute_command.side_effect = _execute

    with patch(
        "pandaplot.gui.components.tabs.tab_container_command_manager.MeasurementAnalysisWizard",
        return_value=wizard,
    ):
        manager = TabContainerCommandManager(app_context)
        manager.analyze_measurements_for_dataset("ds")

    calls = executor.execute_command.call_args_list
    assert len(calls) == 2
    assert isinstance(calls[0].args[0], AnalyzeMeasurementsCommand)
    chart_command = calls[1].args[0]
    assert isinstance(chart_command, CreateChartFromWizardCommand)
    assert chart_command.dataset_id == "summary-dataset"


def test_cancelled_wizard_does_not_execute_a_command():
    app_context, _project, dataset = _context()
    wizard = Mock()
    wizard.exec.return_value = QDialog.DialogCode.Rejected

    with patch(
        "pandaplot.gui.components.tabs.tab_container_command_manager.MeasurementAnalysisWizard",
        return_value=wizard,
    ):
        TabContainerCommandManager(app_context).analyze_measurements_for_dataset(dataset.id)

    app_context.get_command_executor.return_value.execute_command.assert_not_called()
