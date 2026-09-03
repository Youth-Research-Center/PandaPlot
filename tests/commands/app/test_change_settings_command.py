"""Tests for ChangeSettingsCommand: settings changes (theme included) must be
undoable/redoable through CommandExecutor, not applied outside its history."""
import logging
from unittest.mock import Mock

from pandaplot.commands.app.change_settings_command import ChangeSettingsCommand
from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.state.config import Theme
from pandaplot.services.config.config_manager import ConfigManager


def _config_manager(tmp_path):
    manager = ConfigManager(EventBus(), config_path=tmp_path / "config.json")
    manager.load()
    return manager


def test_execute_applies_mapping_and_undo_restores_prior_values(tmp_path):
    config_manager = _config_manager(tmp_path)
    mapping = {"appearance": {"theme": "dark"}}
    command = ChangeSettingsCommand(Mock(), mapping, config_manager=config_manager)

    assert command.execute() is CommandResult.SUCCESS
    assert config_manager.config.appearance.theme == Theme.DARK

    command.undo()
    assert config_manager.config.appearance.theme == Theme.SYSTEM

    command.redo()
    assert config_manager.config.appearance.theme == Theme.DARK


def test_execute_returns_false_when_mapping_matches_current_settings(tmp_path):
    config_manager = _config_manager(tmp_path)
    current_theme = config_manager.config.appearance.theme.value
    mapping = {"appearance": {"theme": current_theme}}
    command = ChangeSettingsCommand(Mock(), mapping, config_manager=config_manager)

    assert command.execute() is CommandResult.NOOP


def test_reapplying_settings_dialog_with_no_changes_logs_quietly_not_a_warning(tmp_path, caplog):
    """Reported live: re-accepting the Settings dialog with nothing changed
    (e.g. Apply then OK) logged 'Command execution failed: ChangeSettingsCommand'
    as a WARNING even though nothing actually failed."""
    config_manager = _config_manager(tmp_path)
    current_theme = config_manager.config.appearance.theme.value
    mapping = {"appearance": {"theme": current_theme}}
    executor = CommandExecutor()

    with caplog.at_level(logging.DEBUG, logger="CommandExecutor"):
        executed = executor.execute_command(
            ChangeSettingsCommand(Mock(), mapping, config_manager=config_manager)
        )

    assert executed is False
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == []
    assert any("no-op" in r.message for r in caplog.records)


def test_undo_only_touches_fields_present_in_mapping(tmp_path):
    """old_mapping must be restricted to the touched fields so undo doesn't
    clobber other appearance fields (e.g. accent_color) left untouched."""
    config_manager = _config_manager(tmp_path)
    config_manager.update({"appearance": {"accent_color": "#123456"}})

    mapping = {"appearance": {"theme": "dark"}}
    command = ChangeSettingsCommand(Mock(), mapping, config_manager=config_manager)
    command.execute()
    command.undo()

    assert config_manager.config.appearance.theme == Theme.SYSTEM
    assert config_manager.config.appearance.accent_color == "#123456"


def test_theme_change_is_undoable_through_command_executor(tmp_path):
    """Reproduces the reported bug: after accepting a settings/theme change,
    Undo in the Edit menu must become enabled and actually revert it."""
    config_manager = _config_manager(tmp_path)
    executor = CommandExecutor()

    mapping = {"appearance": {"theme": "dark"}}
    executed = executor.execute_command(
        ChangeSettingsCommand(Mock(), mapping, config_manager=config_manager)
    )

    assert executed is True
    assert executor.can_undo() is True
    assert config_manager.config.appearance.theme == Theme.DARK

    executor.undo()
    assert config_manager.config.appearance.theme == Theme.SYSTEM
    assert executor.can_redo() is True
