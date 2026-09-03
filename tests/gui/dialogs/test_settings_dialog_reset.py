"""Tests for the Settings dialog's "Reset to Defaults" button.

Reported in code review: reset_to_defaults() called ConfigManager.reset()
directly, bypassing the ChangeSettingsCommand every other settings change
(Apply/OK) now goes through -- making a reset both un-undoable and, worse,
stranding the pre-reset settings with no way back.
"""
import sys
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from pandaplot.app import build_app_context
from pandaplot.gui.dialogs.settings_dialog import SettingsDialog
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.state.config import Theme
from pandaplot.services.config.config_manager import ConfigManager


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _isolated_dialog(tmp_path):
    _qapp()
    app_context = build_app_context()
    dialog = SettingsDialog(app_context)
    dialog._config_manager = ConfigManager(EventBus(), config_path=tmp_path / "config.json")
    dialog._config_manager.load()
    dialog.load_current_settings()
    return dialog


def test_reset_to_defaults_is_undoable(tmp_path):
    dialog = _isolated_dialog(tmp_path)
    dialog.theme_combo.setCurrentText("Dark")
    dialog.apply_settings()
    assert dialog._config_manager.config.appearance.theme == Theme.DARK

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog.reset_to_defaults()

    assert dialog._config_manager.config.appearance.theme == Theme.SYSTEM

    dialog.app_context.get_command_executor().undo()
    assert dialog._config_manager.config.appearance.theme == Theme.DARK


def test_reset_to_defaults_declined_leaves_settings_untouched(tmp_path):
    dialog = _isolated_dialog(tmp_path)
    dialog.theme_combo.setCurrentText("Dark")
    dialog.apply_settings()

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        dialog.reset_to_defaults()

    assert dialog._config_manager.config.appearance.theme == Theme.DARK
    assert dialog.app_context.get_command_executor().can_undo() is True


def test_reset_to_defaults_does_not_touch_recent_projects(tmp_path):
    """Only auto_save/appearance/editor/chart_display are in scope --
    session/window state must survive a reset untouched."""
    dialog = _isolated_dialog(tmp_path)
    dialog._config_manager.config.recent_projects.append("some/project.pandaplot")
    dialog.theme_combo.setCurrentText("Dark")
    dialog.apply_settings()

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog.reset_to_defaults()

    assert dialog._config_manager.config.recent_projects == ["some/project.pandaplot"]


def test_reset_to_defaults_is_a_noop_when_already_default(tmp_path):
    dialog = _isolated_dialog(tmp_path)
    executor = dialog.app_context.get_command_executor()

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog.reset_to_defaults()

    assert executor.can_undo() is False
