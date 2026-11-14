"""Tests for the PreprocessingPanel's status messages (icon + text instead of emoji-prefixed preview text)."""
from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.analysis import PreprocessingMethod
from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.components.common.status_message import StatusKind
from pandaplot.gui.components.sidebar.preprocessing.preprocessing_panel import PreprocessingPanel
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.utils.errors import UserFacingError
from tests.gui.icon_testing import assert_tinted, strongest_pixel
from tests.gui.theme_testing import design_tokens


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.get_manager.return_value.get_design_tokens.return_value = design_tokens()
    return ctx


@pytest.fixture
def panel(app_context):
    panel = PreprocessingPanel(app_context)
    panel.current_dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]}))
    panel.current_dataset_id = "ds-1"
    panel.update_column_choices()
    return panel


def _select_first_column(panel: PreprocessingPanel) -> None:
    panel.column_list.item(0).setSelected(True)


def test_status_message_sits_directly_above_the_preview_text(panel):
    layout = panel.preview_text.parentWidget().layout()

    assert layout.indexOf(panel.status_message) == layout.indexOf(panel.preview_text) - 1
    assert panel.status_message.isHidden()


def test_no_dataset_is_an_error_status(panel):
    panel.current_dataset = None
    panel.preview_text.setPlainText("stale preview")

    panel.preview()

    assert panel.status_message.kind() is StatusKind.ERROR
    assert panel.status_message.message() == "No dataset selected."
    assert panel.preview_text.toPlainText() == ""


def test_no_selected_column_is_an_error_status(panel):
    panel.preview()

    assert panel.status_message.kind() is StatusKind.ERROR
    assert panel.status_message.message() == "Please select at least one column."


def test_output_range_that_is_not_increasing_is_an_error_status(panel):
    panel.method_combo.setCurrentIndex(panel.method_combo.findData(PreprocessingMethod.MINMAX.value))
    _select_first_column(panel)
    panel.range_min_spin.setValue(5.0)
    panel.range_max_spin.setValue(1.0)

    panel.preview()

    assert panel.status_message.kind() is StatusKind.ERROR
    assert panel.status_message.message() == "Output max must be greater than output min."


def test_preview_error_shows_the_exception_as_an_error_status(panel, monkeypatch):
    _select_first_column(panel)
    monkeypatch.setattr(
        "pandaplot.gui.components.sidebar.preprocessing.preprocessing_panel.PreprocessingEngine.transform",
        Mock(side_effect=UserFacingError("<b>bad</b>")),
    )

    panel.preview()

    assert panel.status_message.kind() is StatusKind.ERROR
    assert panel.status_message.message() == "Preview error: <b>bad</b>"


def test_successful_preview_writes_the_text_and_clears_an_earlier_status(panel):
    panel.preview()
    assert panel.status_message.kind() is StatusKind.ERROR
    _select_first_column(panel)

    panel.preview()

    assert panel.status_message.message() == ""
    assert "Fitted parameters" in panel.preview_text.toPlainText()


def test_apply_success_is_a_success_status(panel, app_context):
    app_context.get_command_executor.return_value.execute_command.return_value = True
    _select_first_column(panel)
    panel.preview_text.setPlainText("old preview")

    panel.apply()

    assert panel.status_message.kind() is StatusKind.SUCCESS
    assert panel.status_message.message() == "Preprocessing applied to 1 column(s)."
    assert panel.preview_text.toPlainText() == ""


def test_apply_failure_is_an_error_status(panel, app_context):
    app_context.get_command_executor.return_value.execute_command.return_value = False
    _select_first_column(panel)

    panel.apply()

    assert panel.status_message.kind() is StatusKind.ERROR
    assert panel.status_message.message() == "Failed to apply. Check that the columns are numeric."


def test_apply_exception_is_an_error_status(panel, app_context):
    app_context.get_command_executor.return_value.execute_command.side_effect = RuntimeError("boom")
    _select_first_column(panel)

    panel.apply()

    assert panel.status_message.kind() is StatusKind.ERROR
    assert panel.status_message.message() == "Couldn't apply the preprocessing: Something went wrong that PandaPlot did not expect. If it keeps happening, please report it."


def test_apply_without_a_dataset_id_is_an_error_status(panel):
    _select_first_column(panel)
    panel.current_dataset_id = None

    panel.apply()

    assert panel.status_message.kind() is StatusKind.ERROR
    assert panel.status_message.message() == "No dataset selected."


def test_clear_inputs_clears_the_status_message(panel):
    panel.preview()
    assert panel.status_message.kind() is StatusKind.ERROR

    panel.clear_inputs()

    assert panel.status_message.message() == ""
    assert panel.status_message.kind() is None


def test_theme_change_retints_the_status_icon(panel, app_context):
    panel.preview()
    app_context.get_manager.return_value.get_design_tokens.return_value["status_danger"] = "#00AA00"

    panel._apply_theme()

    assert_tinted(strongest_pixel(panel.status_message.findChild(IconLabel).pixmap()), "#00AA00")
