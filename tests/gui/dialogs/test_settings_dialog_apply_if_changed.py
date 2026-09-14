"""Tests for SettingsDialog's apply-if-changed logic: both the Apply/OK
button path (apply_settings()) and the dialog-load path
(load_current_settings(), called again whenever _on_config_event fires
while the dialog is open).

A prior attempt at the Apply-button half (PR #386, closed) discarded
execute_command()'s return value, so a failed config write was silently
reported as a successful apply -- Copilot flagged this in review twice and
it was never fixed. It also never touched the dialog-load half at all,
despite closing out the TODO(#214) comment that asked for exactly that.
This test suite guards against both gaps.
"""
import sys
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.dialogs.settings_dialog import SettingsDialog
from pandaplot.models.events.event_bus import EventBus
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


def test_apply_settings_is_a_noop_when_nothing_changed(tmp_path):
    dialog = _isolated_dialog(tmp_path)
    executor = dialog.app_context.get_command_executor()

    changed_signal_handler = Mock()
    dialog.settings_changed.connect(changed_signal_handler)

    with patch.object(executor, "execute_command") as mock_execute:
        dialog.apply_settings()

    mock_execute.assert_not_called()
    changed_signal_handler.assert_not_called()


def test_apply_settings_advances_state_when_something_changed(tmp_path):
    dialog = _isolated_dialog(tmp_path)
    changed_signal_handler = Mock()
    dialog.settings_changed.connect(changed_signal_handler)

    dialog.auto_save_check.setChecked(not dialog.auto_save_check.isChecked())
    dialog.apply_settings()

    changed_signal_handler.assert_called_once()
    assert dialog.original_settings["auto_save"] == dialog.auto_save_check.isChecked()

    # A second Apply with nothing further changed must be a no-op.
    changed_signal_handler.reset_mock()
    executor = dialog.app_context.get_command_executor()
    with patch.object(executor, "execute_command") as mock_execute:
        dialog.apply_settings()
    mock_execute.assert_not_called()
    changed_signal_handler.assert_not_called()


def test_apply_settings_does_not_advance_state_when_command_fails(tmp_path):
    dialog = _isolated_dialog(tmp_path)
    executor = dialog.app_context.get_command_executor()

    changed_signal_handler = Mock()
    dialog.settings_changed.connect(changed_signal_handler)

    dialog.auto_save_check.setChecked(not dialog.auto_save_check.isChecked())
    original_before = dict(dialog.original_settings)

    with patch.object(executor, "execute_command", return_value=False):
        dialog.apply_settings()

    assert dialog.original_settings == original_before
    changed_signal_handler.assert_not_called()


def test_load_current_settings_skips_reapply_when_config_unchanged(tmp_path):
    """TODO(#214) at settings_dialog.py:517 asked for exactly this: reloading
    from an unchanged config (e.g. via _on_config_event firing while the
    dialog is open) must not needlessly re-run apply_settings_to_ui()."""
    dialog = _isolated_dialog(tmp_path)

    with patch.object(dialog, "apply_settings_to_ui") as mock_apply_to_ui:
        dialog.load_current_settings()

    mock_apply_to_ui.assert_not_called()


def test_load_current_settings_still_reapplies_when_config_changed(tmp_path):
    dialog = _isolated_dialog(tmp_path)
    dialog._config_manager.config.appearance.interface_font_size = 14
    dialog._config_manager.save()

    with patch.object(dialog, "apply_settings_to_ui") as mock_apply_to_ui:
        dialog.load_current_settings()

    mock_apply_to_ui.assert_called_once()


def test_unchanged_reload_does_not_discard_pending_accent_pick(tmp_path):
    """Regression: choose_accent_color() writes directly into
    current_settings (there's no accent widget for get_current_settings_from_ui()
    to read back), so an unrelated CONFIG_UPDATED event that reloads an
    unchanged config must not silently revert that pending pick -- even
    though apply_settings_to_ui() is skipped and the button's paint never
    visibly changes, get_current_settings_from_ui() reads accent_color back
    out of current_settings on the next Apply."""
    dialog = _isolated_dialog(tmp_path)
    dialog.current_settings["accent_color"] = "#123456"

    dialog.load_current_settings()  # config on disk is unchanged

    assert dialog.current_settings["accent_color"] == "#123456"


def test_reset_to_defaults_resyncs_ui_even_when_config_was_already_default(tmp_path):
    """Regression: Reset to Defaults must always resync the visible widgets
    to the (default) config, even when the persisted config already equals
    the defaults (ChangeSettingsCommand reports NOOP) -- otherwise any
    unsaved dirty widget value the user had before clicking Reset stays on
    screen instead of reverting."""
    from unittest.mock import patch as _patch

    from PySide6.QtWidgets import QMessageBox

    dialog = _isolated_dialog(tmp_path)
    dialog.auto_save_check.setChecked(not dialog.auto_save_check.isChecked())  # dirty, unapplied

    with _patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog.reset_to_defaults()

    assert dialog.auto_save_check.isChecked() == dialog._config_manager.config.auto_save.enabled


def test_accept_settings_closes_when_apply_succeeds(tmp_path):
    dialog = _isolated_dialog(tmp_path)
    dialog.auto_save_check.setChecked(not dialog.auto_save_check.isChecked())

    with patch.object(dialog, "accept") as mock_accept:
        dialog.accept_settings()

    mock_accept.assert_called_once()


def test_accept_settings_closes_when_nothing_changed(tmp_path):
    dialog = _isolated_dialog(tmp_path)

    with patch.object(dialog, "accept") as mock_accept:
        dialog.accept_settings()

    mock_accept.assert_called_once()


def test_accept_settings_does_not_close_when_apply_fails(tmp_path):
    """Regression: accept_settings() (the OK button) used to call
    self.accept() unconditionally after apply_settings(), so a failed
    config write silently closed the dialog anyway, discarding the edit
    with no indication anything went wrong."""
    dialog = _isolated_dialog(tmp_path)
    executor = dialog.app_context.get_command_executor()
    dialog.auto_save_check.setChecked(not dialog.auto_save_check.isChecked())

    with patch.object(executor, "execute_command", return_value=False):
        with patch.object(dialog, "accept") as mock_accept:
            dialog.accept_settings()

    mock_accept.assert_not_called()
