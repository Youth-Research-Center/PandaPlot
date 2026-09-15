"""Tests for UIController.show_new_project_dialog (#209)."""
import sys
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from pandaplot.gui.controllers.ui_controller import UIController


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_returns_the_trimmed_name_on_accept():
    _qapp()
    controller = UIController()
    with patch("pandaplot.gui.controllers.ui_controller.QInputDialog.getText", return_value=("  My Project  ", True)):
        assert controller.show_new_project_dialog() == "My Project"


def test_returns_none_when_cancelled():
    _qapp()
    controller = UIController()
    with patch("pandaplot.gui.controllers.ui_controller.QInputDialog.getText", return_value=("My Project", False)):
        assert controller.show_new_project_dialog() is None


def test_returns_none_for_a_blank_name_even_if_accepted():
    _qapp()
    controller = UIController()
    with patch("pandaplot.gui.controllers.ui_controller.QInputDialog.getText", return_value=("   ", True)):
        assert controller.show_new_project_dialog() is None


def test_prefills_the_default_name():
    _qapp()
    controller = UIController()
    with patch("pandaplot.gui.controllers.ui_controller.QInputDialog.getText", return_value=("", True)) as get_text:
        controller.show_new_project_dialog(default_name="Untitled")
    assert get_text.call_args.kwargs.get("text") == "Untitled"
