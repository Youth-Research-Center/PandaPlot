"""Tests for TransformController.apply_transformation error propagation."""

from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.transform.transform_controller import TransformController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState
from pandaplot.utils.error_messages import ErrorDescription


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


def test_command_failure_with_a_description_emits_its_plain_reason_and_next_step(ctx):
    app_context, _ = ctx
    controller = TransformController(app_context)

    def fake_execute(command):
        command.error_message = "unsupported operand type(s) for +: 'int' and 'str'"
        command.error_description = ErrorDescription(
            reason="PandaPlot could not process this data with these settings.",
            next_step="Check that the selected columns contain numbers.",
            details="TypeError: unsupported operand type(s) for +: 'int' and 'str'",
        )
        return False

    app_context.get_command_executor.return_value.execute_command.side_effect = fake_execute
    received = []
    controller.transform_failed.connect(lambda dataset_id, message: received.append(message))

    assert controller.apply_transformation("ds-1", "a", "a_new", "x * 2") is False

    assert received == ["PandaPlot could not process this data with these settings. Check that the selected columns contain numbers."]
    assert "unsupported operand" not in received[0]


def test_unexpected_exception_in_apply_emits_plain_text_without_type_names(ctx):
    app_context, _ = ctx
    controller = TransformController(app_context)
    app_context.get_command_executor.side_effect = TypeError("unsupported operand type(s) for +: 'int' and 'str'")
    received = []
    controller.transform_failed.connect(lambda dataset_id, message: received.append(message))

    assert controller.apply_transformation("ds-1", "a", "a_new", "x * 2") is False

    assert received == ["PandaPlot could not process this data with these settings. Check that the selected columns contain the kind of values this needs, for example numbers."]


def test_preview_failure_returns_plain_text_without_library_wording(ctx):
    app_context, _ = ctx
    controller = TransformController(app_context)

    preview = controller.create_preview("ds-1", "a", "x + 'text'")

    assert preview is not None
    assert preview["error"].startswith("PandaPlot could not process this data with these settings.")
    assert "Preview generation failed" not in preview["error"]
    assert "operand" not in preview["error"]
    assert "TypeError" not in preview["error"]


def test_formula_flags_are_threaded_into_the_transform_config(ctx):
    """Issue #154: the panel's "save as formula" / "live" checkboxes have to
    reach TransformColumnCommand, which is what actually registers the spec."""
    app_context, _ = ctx
    controller = TransformController(app_context)

    captured = []
    executor = Mock()
    executor.execute_command.side_effect = lambda command: captured.append(command.transform_config) or True
    app_context.get_command_executor.return_value = executor

    controller.apply_transformation(
        dataset_id="ds-1",
        source_column="a",
        new_column_name="a_x2",
        function_code="x * 2",
        as_formula=True,
        live=True,
    )

    assert captured[0]["as_formula"] is True
    assert captured[0]["live"] is True


def test_formula_flags_default_to_off(ctx):
    app_context, _ = ctx
    controller = TransformController(app_context)

    captured = []
    executor = Mock()
    executor.execute_command.side_effect = lambda command: captured.append(command.transform_config) or True
    app_context.get_command_executor.return_value = executor

    controller.apply_transformation(
        dataset_id="ds-1", source_column="a", new_column_name="a_x2", function_code="x * 2",
    )

    assert captured[0]["as_formula"] is False
    assert captured[0]["live"] is False
