"""Tests for TransformController.apply_transformation error propagation."""

from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.transform.transform_controller import TransformController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def ctx():
    QApplication.instance() or QApplication([])
    project = Project(name="P")
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"a": [1, 2, 3]}))
    project.add_item(dataset)

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.current_project = project
    app_context.app_state = app_state
    return app_context, dataset


def test_command_execution_failure_surfaces_the_commands_specific_reason(ctx):
    """When the command itself fails (not one of the controller's own
    pre-checks), the transform_failed signal must carry the command's
    error_message instead of a generic "Failed to execute" string."""
    app_context, _ = ctx
    controller = TransformController(app_context)

    def fake_execute(command):
        command.error_message = "Expression referenced an out-of-range index"
        return False

    executor = Mock()
    executor.execute_command.side_effect = fake_execute
    app_context.get_command_executor.return_value = executor

    received = []
    controller.transform_failed.connect(lambda dataset_id, message: received.append(message))

    # "b" isn't in the dataset -- valid per the controller's own pre-checks
    # (which only check `source_column`), so the failure must come from the
    # command itself, e.g. an expression referencing an out-of-range index.
    result = controller.apply_transformation(
        dataset_id="ds-1",
        source_column="a",
        new_column_name="a_new",
        function_code="x * 2",
        replace_existing=False,
    )

    assert result is False
    assert received == ["Expression referenced an out-of-range index"]
