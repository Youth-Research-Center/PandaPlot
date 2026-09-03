"""Tests for TabContainerCommandManager, extracted from TabContainer per issue #251
('TabContainer also carries command-dispatch logic beyond tab-type knowledge')."""
from unittest.mock import Mock, patch

from pandaplot.gui.components.tabs.tab_container_command_manager import TabContainerCommandManager


def _manager(app_context):
    return TabContainerCommandManager(app_context)


@patch("pandaplot.gui.components.tabs.tab_container_command_manager.NewProjectCommand")
def test_handle_new_project_executes_new_project_command(mock_command_cls):
    app_context = Mock()
    manager = _manager(app_context)

    manager.handle_new_project()

    mock_command_cls.assert_called_once_with(app_context)
    app_context.get_command_executor.return_value.execute_command.assert_called_once_with(
        mock_command_cls.return_value
    )


@patch("pandaplot.gui.components.tabs.tab_container_command_manager.OpenProjectCommand")
def test_handle_open_project_executes_open_project_command(mock_command_cls):
    app_context = Mock()
    manager = _manager(app_context)

    manager.handle_open_project()

    mock_command_cls.assert_called_once_with(app_context)
    app_context.get_command_executor.return_value.execute_command.assert_called_once_with(
        mock_command_cls.return_value
    )


@patch("pandaplot.gui.components.tabs.tab_container_command_manager.LoadProjectCommand")
def test_handle_recent_project_executes_load_project_command_with_the_path(mock_command_cls):
    app_context = Mock()
    manager = _manager(app_context)

    manager.handle_recent_project("/path/to/project.pplot")

    mock_command_cls.assert_called_once_with(app_context, "/path/to/project.pplot")
    app_context.get_command_executor.return_value.execute_command.assert_called_once_with(
        mock_command_cls.return_value
    )


@patch("pandaplot.gui.components.tabs.tab_container_command_manager.LoadProjectCommand")
def test_handle_example_project_executes_load_project_command_with_the_path(mock_command_cls):
    app_context = Mock()
    manager = _manager(app_context)

    manager.handle_example_project("/examples/demo.pplot")

    mock_command_cls.assert_called_once_with(app_context, "/examples/demo.pplot")
    app_context.get_command_executor.return_value.execute_command.assert_called_once_with(
        mock_command_cls.return_value
    )


def test_handle_import_data_creates_a_project_first_when_none_is_loaded():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = False
    manager = _manager(app_context)
    manager.handle_new_project = Mock()

    with patch(
        "pandaplot.commands.project.dataset.import_data_command.ImportDataCommand"
    ) as mock_command_cls:
        manager.handle_import_data()

    manager.handle_new_project.assert_called_once()
    mock_command_cls.assert_called_once_with(app_context)
    app_context.get_command_executor.return_value.execute_command.assert_called_once_with(
        mock_command_cls.return_value
    )


def test_handle_import_data_skips_new_project_when_one_is_already_loaded():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = True
    manager = _manager(app_context)
    manager.handle_new_project = Mock()

    with patch("pandaplot.commands.project.dataset.import_data_command.ImportDataCommand"):
        manager.handle_import_data()

    manager.handle_new_project.assert_not_called()


@patch("pandaplot.gui.components.tabs.tab_container_command_manager.CreateEmptyDatasetCommand")
def test_handle_create_dataset_creates_a_project_first_when_none_is_loaded(mock_command_cls):
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = False
    manager = _manager(app_context)
    manager.handle_new_project = Mock()

    manager.handle_create_dataset()

    manager.handle_new_project.assert_called_once()
    mock_command_cls.assert_called_once_with(app_context)
    app_context.get_command_executor.return_value.execute_command.assert_called_once_with(
        mock_command_cls.return_value
    )


@patch("pandaplot.gui.components.tabs.tab_container_command_manager.CreateEmptyDatasetCommand")
def test_handle_create_dataset_skips_new_project_when_one_is_already_loaded(mock_command_cls):
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = True
    manager = _manager(app_context)
    manager.handle_new_project = Mock()

    manager.handle_create_dataset()

    manager.handle_new_project.assert_not_called()
    mock_command_cls.assert_called_once_with(app_context)


@patch("pandaplot.gui.components.tabs.tab_container_command_manager.CreateChartFromWizardCommand")
def test_handle_create_chart_executes_wizard_command_without_a_dataset(mock_command_cls):
    app_context = Mock()
    manager = _manager(app_context)
    manager.handle_new_project = Mock()

    manager.handle_create_chart()

    mock_command_cls.assert_called_once_with(app_context)
    app_context.get_command_executor.return_value.execute_command.assert_called_once_with(
        mock_command_cls.return_value
    )
    # Unlike handle_create_dataset/handle_import_data, this doesn't pre-create
    # a project -- CreateChartFromWizardCommand offers to do that itself.
    manager.handle_new_project.assert_not_called()


@patch("pandaplot.gui.components.tabs.tab_container_command_manager.CreateChartFromWizardCommand")
def test_create_chart_from_dataset_builds_the_wizard_command(mock_command_cls):
    dataset_item = Mock()
    dataset_item.parent_id = "folder-1"

    project = Mock()
    project.find_item.return_value = dataset_item

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state

    manager = _manager(app_context)

    manager.create_chart_from_dataset("ds-1", preselected_column_ids=["col-rev"])

    mock_command_cls.assert_called_once_with(
        app_context, dataset_id="ds-1", preselected_column_ids=["col-rev"]
    )
    app_context.get_command_executor.return_value.execute_command.assert_called_once_with(
        mock_command_cls.return_value
    )


def test_create_chart_from_dataset_warns_and_returns_when_dataset_not_found():
    project = Mock()
    project.find_item.return_value = None

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state

    manager = _manager(app_context)

    manager.create_chart_from_dataset("missing-ds")

    app_context.get_command_executor.return_value.execute_command.assert_not_called()
