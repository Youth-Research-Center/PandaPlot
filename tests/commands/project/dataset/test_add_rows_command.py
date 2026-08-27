"""Logging-only tests for AddRowsCommand's failure paths.

AddRowsCommand does not otherwise have a dedicated test file; these tests
cover only the warning logging added for genuine failures in execute() (see
issue-184-audit-command-logging).
"""

import logging
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.project.dataset.add_rows_command import AddRowsCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def mock_app_context():
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    ui_controller = Mock(spec=UIController)

    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = ui_controller
    app_state.event_bus = Mock()
    app_state.event_bus.emit = Mock()
    app_state.has_project = True

    return app_context, app_state, ui_controller


@pytest.fixture
def project_with(mock_app_context):
    _, app_state, _ = mock_app_context

    def _build(dataset):
        project = Mock()
        project.find_item = Mock(return_value=dataset)
        app_state.current_project = project
        return project

    return _build


def test_execute_logs_a_warning_when_no_reference_positions(mock_app_context, caplog):
    app_context, _, _ = mock_app_context
    command = AddRowsCommand(app_context, "ds-1", reference_positions=[])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "no reference positions" in caplog.text.lower()


def test_execute_logs_a_warning_when_no_project_open(mock_app_context, caplog):
    app_context, app_state, _ = mock_app_context
    app_state.has_project = False
    command = AddRowsCommand(app_context, "ds-1", reference_positions=[0])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "no project" in caplog.text.lower()


def test_execute_logs_a_warning_when_dataset_not_found(mock_app_context, project_with, caplog):
    app_context, _, _ = mock_app_context
    project_with(None)

    command = AddRowsCommand(app_context, "missing-ds", reference_positions=[0])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "missing-ds" in caplog.text


def test_execute_logs_a_warning_when_item_is_not_a_dataset(mock_app_context, project_with, caplog):
    app_context, _, _ = mock_app_context
    project_with(Mock(spec=[]))  # not a Dataset instance

    command = AddRowsCommand(app_context, "ds-1", reference_positions=[0])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "ds-1" in caplog.text


def test_execute_logs_a_warning_when_dataset_has_no_structure(mock_app_context, project_with, caplog):
    app_context, _, _ = mock_app_context
    dataset = Mock(spec=Dataset)
    dataset.data = None
    project_with(dataset)

    command = AddRowsCommand(app_context, "ds-1", reference_positions=[0])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "ds-1" in caplog.text


def test_execute_logs_a_warning_when_reference_position_out_of_bounds(mock_app_context, project_with, caplog):
    app_context, _, _ = mock_app_context
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
    project_with(dataset)

    command = AddRowsCommand(app_context, "ds-1", reference_positions=[5])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "5" in caplog.text


def test_cleanup_releases_the_original_data_snapshot():
    app_context = Mock(spec=AppContext)
    app_context.get_app_state.return_value = Mock(spec=AppState)
    app_context.get_ui_controller.return_value = Mock()

    command = AddRowsCommand(app_context, "ds-1", reference_positions=[0])
    command.original_data = pd.DataFrame({"a": [1, 2, 3]})

    command.cleanup()

    assert command.original_data is None
