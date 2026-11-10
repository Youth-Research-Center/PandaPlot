"""Tests for UIController.show_action_or_cancel."""
from unittest.mock import Mock, patch

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QColorDialog

from pandaplot.gui.controllers.ui_controller import UIController


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@patch("pandaplot.gui.controllers.ui_controller.QMessageBox")
def test_show_action_or_cancel_returns_true_for_the_action_button(mock_message_box_cls):
    mock_box = mock_message_box_cls.return_value
    action_button = Mock(name="action_button")
    cancel_button = Mock(name="cancel_button")
    mock_box.addButton.side_effect = [action_button, cancel_button]
    mock_box.clickedButton.return_value = action_button

    controller = UIController()
    result = controller.show_action_or_cancel("Title", "Message", "Create Project")

    assert result is True
    mock_box.exec.assert_called_once()


@patch("pandaplot.gui.controllers.ui_controller.QMessageBox")
def test_show_action_or_cancel_returns_false_for_cancel(mock_message_box_cls):
    mock_box = mock_message_box_cls.return_value
    action_button = Mock(name="action_button")
    cancel_button = Mock(name="cancel_button")
    mock_box.addButton.side_effect = [action_button, cancel_button]
    mock_box.clickedButton.return_value = cancel_button

    controller = UIController()
    result = controller.show_action_or_cancel("Title", "Message", "Create Project")

    assert result is False


@patch("pandaplot.gui.controllers.ui_controller.QMessageBox")
def test_show_action_or_cancel_passes_the_action_label_to_add_button(mock_message_box_cls):
    mock_box = mock_message_box_cls.return_value
    mock_box.addButton.side_effect = [Mock(), Mock()]
    mock_box.clickedButton.return_value = None

    controller = UIController()
    controller.show_action_or_cancel("Title", "Message", "Create Project")

    first_call_args = mock_box.addButton.call_args_list[0].args
    assert first_call_args[0] == "Create Project"


@pytest.mark.parametrize(("chosen", "expected"), [
    (("/tmp/plan", "PNG image (*.png)"), "/tmp/plan.png"),
    (("/tmp/plan.PNG", "PNG image (*.png)"), "/tmp/plan.PNG"),
    (("", ""), None),
])
@patch("pandaplot.gui.controllers.ui_controller.QFileDialog.getSaveFileName")
def test_get_save_file_path_adds_a_missing_extension(mock_save, chosen, expected):
    mock_save.return_value = chosen

    assert UIController().get_save_file_path("Export Plan", "Plan.png", "PNG image (*.png)", ".png") == expected
    assert mock_save.call_args.args[1:] == ("Export Plan", "Plan.png", "PNG image (*.png)")


@pytest.mark.parametrize(("picked", "expected"), [
    (QColor(255, 0, 0), "#ff0000"),
    (QColor(255, 0, 0, 128), "#80ff0000"),
    (QColor(), None),
])
@patch("pandaplot.gui.controllers.ui_controller.QColorDialog.getColor")
def test_get_color_returns_hex_with_alpha_only_when_translucent(mock_get_color, picked, expected):
    mock_get_color.return_value = picked

    assert UIController().get_color("Fill Colour", "#80112233", with_alpha=True) == expected

    initial, _parent, title, options = mock_get_color.call_args.args
    assert initial == QColor("#80112233")
    assert title == "Fill Colour"
    assert options & QColorDialog.ColorDialogOption.ShowAlphaChannel


@patch("pandaplot.gui.controllers.ui_controller.QColorDialog.getColor", return_value=QColor("#123456"))
def test_get_color_hides_the_alpha_channel_by_default(mock_get_color):
    UIController().get_color("Stroke Colour", "#000000")

    assert not mock_get_color.call_args.args[3] & QColorDialog.ColorDialogOption.ShowAlphaChannel


def _description(*, next_step: str = "Try again.", details: str = "KeyError: x"):
    from pandaplot.utils.error_messages import ErrorDescription

    return ErrorDescription(reason="Because.", next_step=next_step, details=details)


def test_build_error_box_sets_text_informative_text_details_icon_and_escape_button():
    from PySide6.QtWidgets import QMessageBox

    from pandaplot.gui.controllers.ui_controller import build_error_box

    box = build_error_box(None, "Save Failed", "Couldn't save.", _description())
    try:
        assert box.windowTitle() == "Save Failed"
        assert box.text() == "Couldn't save."
        assert box.informativeText() == "Because.\n\nTry again."
        assert box.detailedText() == "KeyError: x"
        assert box.icon() == QMessageBox.Icon.Critical
        assert box.escapeButton() is box.button(QMessageBox.StandardButton.Ok)
        assert box.defaultButton() is box.button(QMessageBox.StandardButton.Ok)
    finally:
        box.deleteLater()


def test_build_error_box_without_next_step_or_details():
    from pandaplot.gui.controllers.ui_controller import build_error_box

    box = build_error_box(None, "T", "Couldn't.", _description(next_step="", details=""))
    try:
        assert box.informativeText() == "Because."
        assert box.detailedText() == ""
    finally:
        box.deleteLater()


@patch("pandaplot.gui.controllers.ui_controller.QMessageBox")
def test_show_error_message_without_error_calls_critical(mock_message_box_cls):
    parent = Mock()
    UIController(parent).show_error_message("Title", "Message")
    mock_message_box_cls.critical.assert_called_once_with(parent, "Title", "Message")
    mock_message_box_cls.assert_not_called()


@patch("pandaplot.gui.controllers.ui_controller.QMessageBox")
def test_show_error_message_with_exception_describes_it_and_executes_the_box(mock_message_box_cls):
    UIController(None).show_error_message("Title", "Couldn't open.", error=FileNotFoundError("/x"))
    mock_message_box_cls.critical.assert_not_called()
    box = mock_message_box_cls.return_value
    box.setText.assert_called_once_with("Couldn't open.")
    assert "could not be found" in box.setInformativeText.call_args.args[0]
    box.setDetailedText.assert_called_once_with("FileNotFoundError: /x")
    box.exec.assert_called_once_with()


@patch("pandaplot.gui.controllers.ui_controller.QMessageBox")
def test_show_error_message_accepts_a_ready_description(mock_message_box_cls):
    UIController(None).show_error_message("Title", "Couldn't.", error=_description(details=""))
    box = mock_message_box_cls.return_value
    box.setInformativeText.assert_called_once_with("Because.\n\nTry again.")
    box.setDetailedText.assert_not_called()
    box.exec.assert_called_once_with()
