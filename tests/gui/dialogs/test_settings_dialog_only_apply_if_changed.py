import sys
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.gui.dialogs.settings_dialog import SettingsDialog
from pandaplot.models.events.event_bus import EventBus
from pandaplot.services.config.config_manager import ConfigManager


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_apply_settings_only_when_changed(tmp_path):
    _qapp()
    app_context = build_app_context()
    config_manager = ConfigManager(EventBus(), config_path=tmp_path / "config.json")
    config_manager.load()

    mock_executor = MagicMock()
    app_context._managers[CommandExecutor] = mock_executor

    dialog = SettingsDialog(app_context)
    dialog._config_manager = config_manager
    dialog.load_current_settings()

    changed_signal_handler = MagicMock()
    dialog.settings_changed.connect(changed_signal_handler)

    # First call with no UI modifications
    dialog.apply_settings()

    assert mock_executor.execute_command.call_count == 0
    assert changed_signal_handler.call_count == 0

    # Modify a setting
    dialog.auto_save_check.setChecked(not dialog.auto_save_check.isChecked())
    dialog.apply_settings()

    assert mock_executor.execute_command.call_count == 1
    assert changed_signal_handler.call_count == 1

    # Second apply without changes should do nothing
    dialog.apply_settings()
    assert mock_executor.execute_command.call_count == 1
    assert changed_signal_handler.call_count == 1
