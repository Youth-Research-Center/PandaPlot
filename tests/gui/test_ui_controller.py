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
