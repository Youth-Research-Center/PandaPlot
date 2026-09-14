# change_settings_command.py
# Command wrapping an application settings change so it can be undone.

from typing import Any, Mapping, Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.config.config_manager import ConfigManager


class ChangeSettingsCommand(Command):
    """
    Apply a partial settings mapping (as built by SettingsDialog) through
    ConfigManager, capturing the previous values of only the touched fields
    so the change -- theme included -- can be undone/redone like any other
    edit.
    """

    def __init__(
        self,
        app_context: AppContext,
        mapping: Mapping[str, Any],
        *,
        config_manager: Optional[ConfigManager] = None,
    ):
        super().__init__()
        # Accept an explicit ConfigManager (e.g. SettingsDialog's own
        # instance, which tests point at an isolated config file) rather than
        # always resolving it fresh from app_context -- the two can diverge.
        self.config_manager = config_manager or app_context.get_manager(ConfigManager)
        self.new_mapping = mapping
        self.old_mapping: Optional[dict[str, Any]] = None

    @override
    def marks_project_modified(self) -> bool:
        """Only touches ConfigManager (app-level settings), never the
        project itself, so it must not flag the project as having unsaved
        changes."""
        return False

    @override
    def execute(self) -> CommandResult:
        before = self.config_manager.as_dict()
        self.old_mapping = self._extract_matching(before, self.new_mapping)
        if self.old_mapping == self.new_mapping:
            # Apply/OK with nothing actually changed (e.g. re-accepting the
            # dialog without touching a field) -- not a failure worth
            # warning about.
            self.logger.debug("ChangeSettingsCommand: no changes to apply, skipping")
            return CommandResult.NOOP
        return self._apply_and_save(self.new_mapping)

    @override
    def undo(self) -> CommandResult:
        if self.old_mapping is None:
            return CommandResult.FAILURE
        return self._apply_and_save(self.old_mapping)

    @override
    def redo(self) -> CommandResult:
        return self._apply_and_save(self.new_mapping)

    def _apply_and_save(self, mapping: Mapping[str, Any]) -> CommandResult:
        """Apply `mapping` in memory and persist it, reporting FAILURE if
        the disk write didn't actually succeed -- ConfigManager.save()
        catches every write exception internally (its own documented
        "defensive" design), so update(..., save=True) alone can't tell a
        real disk failure from a successful write. Saving explicitly here,
        instead, surfaces save()'s own boolean result."""
        self.config_manager.update(mapping, save=False)
        if not self.config_manager.save():
            return CommandResult.FAILURE
        return CommandResult.SUCCESS

    @staticmethod
    def _extract_matching(source: Mapping[str, Any], mapping: Mapping[str, Any]) -> dict[str, Any]:
        """Pick out of `source` only the sections/fields present in `mapping`,
        so undo restores exactly the fields this command touched and leaves
        everything else (e.g. recent_projects, session state) untouched."""
        matched: dict[str, Any] = {}
        for section, fields in mapping.items():
            src_section = source.get(section)
            if not isinstance(fields, Mapping) or not isinstance(src_section, Mapping):
                continue
            matched[section] = {key: src_section.get(key) for key in fields}
        return matched

    def __repr__(self):
        return "ChangeSettingsCommand()"
