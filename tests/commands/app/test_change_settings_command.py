"""Tests for ChangeSettingsCommand: settings changes (theme included) must be
undoable/redoable through CommandExecutor, not applied outside its history."""
import logging
from unittest.mock import Mock, patch

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


def test_marks_project_modified_is_false(tmp_path):
    """Regression (PR #235 review): this command only touches ConfigManager
    (app-level settings), never the project -- CommandExecutor's generic
    dirty-tracking hook must not flag the project as having unsaved changes
    for a settings change."""
    command = ChangeSettingsCommand(Mock(), {}, config_manager=_config_manager(tmp_path))
    assert command.marks_project_modified() is False


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


def test_execute_reports_failure_when_disk_write_fails(tmp_path):
    """Regression (PR #390 review, Copilot): ConfigManager.save() catches
    every write exception and logs, so execute() previously always returned
    SUCCESS after calling update(..., save=True) regardless of whether the
    write actually reached disk -- SettingsDialog's apply-if-changed guard
    (which relies on this return value) would then silently advance
    original_settings and emit settings_changed for an edit that was never
    actually persisted. execute() must reflect the real save outcome."""
    config_manager = _config_manager(tmp_path)
    mapping = {"appearance": {"theme": "dark"}}
    command = ChangeSettingsCommand(Mock(), mapping, config_manager=config_manager)

    with patch.object(config_manager, "save", return_value=False):
        result = command.execute()

    assert result is CommandResult.FAILURE
    # A follow-up finding (same PR review) on the first version of this fix:
    # applying the mapping in memory before checking save() left the config
    # holding the never-persisted value even on FAILURE, so a retry of the
    # identical edit hit the "already matches, nothing to apply" NOOP branch
    # instead of attempting another save. Failure must roll the in-memory
    # config back to its pre-attempt value, so FAILURE really means no
    # effective change.
    assert config_manager.config.appearance.theme == Theme.SYSTEM


def test_execute_can_be_retried_after_a_failed_save(tmp_path):
    config_manager = _config_manager(tmp_path)
    mapping = {"appearance": {"theme": "dark"}}
    command = ChangeSettingsCommand(Mock(), mapping, config_manager=config_manager)

    with patch.object(config_manager, "save", return_value=False):
        assert command.execute() is CommandResult.FAILURE

    # Retrying the identical edit must actually attempt another save --
    # not silently no-op because the (rolled-back) config already "matches".
    retry = ChangeSettingsCommand(Mock(), mapping, config_manager=config_manager)
    assert retry.execute() is CommandResult.SUCCESS
    assert config_manager.config.appearance.theme == Theme.DARK


def test_undo_reports_failure_when_disk_write_fails(tmp_path):
    config_manager = _config_manager(tmp_path)
    mapping = {"appearance": {"theme": "dark"}}
    command = ChangeSettingsCommand(Mock(), mapping, config_manager=config_manager)
    command.execute()

    with patch.object(config_manager, "save", return_value=False):
        result = command.undo()

    assert result is CommandResult.FAILURE


def test_redo_reports_failure_when_disk_write_fails(tmp_path):
    config_manager = _config_manager(tmp_path)
    mapping = {"appearance": {"theme": "dark"}}
    command = ChangeSettingsCommand(Mock(), mapping, config_manager=config_manager)
    command.execute()
    command.undo()

    with patch.object(config_manager, "save", return_value=False):
        result = command.redo()

    assert result is CommandResult.FAILURE
