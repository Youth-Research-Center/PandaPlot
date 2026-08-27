"""Tests for UIController.show_action_or_cancel."""
from unittest.mock import Mock, patch

import pytest
from PySide6.QtWidgets import QApplication

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
