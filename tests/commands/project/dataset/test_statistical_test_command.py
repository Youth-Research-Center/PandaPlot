"""Tests for StatisticalTestCommand."""

import logging
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.analysis import StatTestType
from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.statistical_test_command import StatisticalTestCommand
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def app_context_with_project():
    rng = np.random.default_rng(7)
    project = Project(name="P")
    dataset = Dataset(
        id="ds-1",
        name="Data",
        data=pd.DataFrame({"A": rng.normal(10, 1, 40), "B": rng.normal(13, 1, 40)}),
    )
    project.add_item(dataset)

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()
    return app_context, project


class TestStatisticalTestCommand:
    def test_execute_adds_results_dataset(self, app_context_with_project):
        app_context, project = app_context_with_project
        command = StatisticalTestCommand(
            app_context, "ds-1", StatTestType.INDEPENDENT_T, ["A", "B"], equal_var=False
        )

        assert command.execute() is CommandResult.SUCCESS

        results = project.find_item(command.result_dataset_id)
        assert results is not None
        assert list(results.data.columns) == ["Metric", "Value"]
        assert command.result.significant is True

    def test_undo_removes_results_dataset(self, app_context_with_project):
        app_context, project = app_context_with_project
        command = StatisticalTestCommand(
            app_context, "ds-1", StatTestType.PEARSON, ["A", "B"]
        )
        command.execute()
        new_id = command.result_dataset_id
        assert project.find_item(new_id) is not None

        assert command.undo() is CommandResult.SUCCESS
        assert project.find_item(new_id) is None

    def test_missing_column_fails_gracefully(self, app_context_with_project):
        app_context, _ = app_context_with_project
        command = StatisticalTestCommand(
            app_context, "ds-1", StatTestType.PEARSON, ["A", "Missing"]
        )
        assert command.execute() is CommandResult.FAILURE
        assert command.result_dataset_id is None
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
        _title, message = app_context.get_ui_controller.return_value.show_error_message.call_args.args
        assert "Missing" in message

    def test_undo_logs_warning_when_nothing_to_undo(self, app_context_with_project, caplog):
        app_context, _ = app_context_with_project
        command = StatisticalTestCommand(
            app_context, "ds-1", StatTestType.PEARSON, ["A", "B"]
        )
        # execute() never ran, so result_dataset_id is unset.

        with caplog.at_level(logging.WARNING):
            assert command.undo() is CommandResult.FAILURE
        assert "cannot undo" in caplog.text.lower()

    def test_execute_surfaces_no_project_loaded_to_the_user(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        app_state.has_project = False
        app_state.current_project = None
        app_context.get_app_state.return_value = app_state

        command = StatisticalTestCommand(app_context, "ds-1", StatTestType.PEARSON, ["A", "B"])
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_cleanup_releases_the_result_dataset_id_and_result(self, app_context_with_project):
        app_context, _ = app_context_with_project
        command = StatisticalTestCommand(
            app_context, "ds-1", StatTestType.PEARSON, ["A", "B"]
        )
        assert command.execute() is CommandResult.SUCCESS
        assert command.result_dataset_id is not None
        assert command.result is not None

        command.cleanup()

        assert command.result_dataset_id is None
        assert command.result is None
