import logging
from typing import Callable, List, Optional

from pandaplot.commands.base_command import Command, CommandResult


class CommandExecutor:
    """
    Command executor that manages command execution, undo/redo functionality.
    This is the central point for executing commands.
    """

    def __init__(self, on_history_changed: Optional[Callable[[], None]] = None,
                 on_project_modified: Optional[Callable[[], None]] = None,
                 on_undo_redo_error: Optional[Callable[[str, str], None]] = None):
        self.logger = logging.getLogger(self.__class__.__name__)

        # Undo/Redo functionality
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.max_undo_levels = 10

        # Called after a command that marks_project_modified() succeeds; wired
        # by app.py to AppState.mark_modified.
        self.on_project_modified = on_project_modified

        # Called whenever can_undo()/can_redo() may have changed; wired by
        # app.py to emit AppEvents.HISTORY_CHANGED.
        self.on_history_changed = on_history_changed

        # Optional hook invoked when a command's undo()/redo() raises
        # instead of returning a CommandResult -- the entire undo/redo
        # history is invalidated in that case (see
        # _invalidate_history_after_failure), and the UI needs to tell the
        # user their history was reset rather than let a later undo/redo
        # silently act on a command whose assumed state no longer holds.
        # Called with (command_description, operation), command_description
        # being command.display_name() (a human-readable label, not the
        # class name) and operation being "undo" or "redo".
        self.on_undo_redo_error = on_undo_redo_error

    def _safe_display_name(self, command: Command) -> str:
        """Resolve command.display_name(), isolating any exception it raises
        so a bad override can't itself break undo/redo failure recovery --
        falls back to the class name, same spirit as _safe_cleanup."""
        try:
            return command.display_name()
        except Exception as e:
            self.logger.error(
                "Error getting display_name() for command '%s': %s",
                command.__class__.__name__, str(e), exc_info=True)
            return command.__class__.__name__

    def _notify_undo_redo_error(self, command_description: str, operation: str) -> None:
        if not self.on_undo_redo_error:
            return
        try:
            self.on_undo_redo_error(command_description, operation)
        except Exception as e:
            # This runs while undo()/redo() is already handling a command
            # failure -- a raising hook (e.g. a Qt dialog) must not prevent
            # the history-changed notification that follows it.
            self.logger.error("Error in on_undo_redo_error hook: %s", str(e), exc_info=True)

    def _notify_project_modified(self, command: Command) -> None:
        if not self.on_project_modified:
            return
        try:
            if command.marks_project_modified():
                self.on_project_modified()
        except Exception as e:
            self.logger.error("Error in on_project_modified hook: %s", str(e), exc_info=True)

    def _notify_history_changed(self) -> None:
        if not self.on_history_changed:
            return
        try:
            self.on_history_changed()
        except Exception as e:
            self.logger.error("Error in on_history_changed hook: %s", str(e), exc_info=True)

    def _warn_if_not_command_result(self, result, command_name: str, method_name: str) -> None:
        """Surface a command whose `execute()`/`undo()`/`redo()` hasn't been
        migrated to return `CommandResult` yet -- some overrides still
        implicitly return `None` on every path (a known, tracked gap, not
        this call's job to fix). Such a value is neither CommandResult.NOOP
        nor CommandResult.FAILURE, so it's silently treated as success below,
        same as it would have been under the old bool contract -- this only
        makes that fact loud instead of invisible, so remaining stragglers
        are easy to find and migrate incrementally instead of a single
        all-or-nothing conversion that would risk breaking every one of them
        at once.
        """
        if not isinstance(result, CommandResult):
            self.logger.warning(
                "%s.%s() returned %r instead of a CommandResult -- treating as "
                "success for backward compatibility. This command needs migrating.",
                command_name, method_name, result,
            )

    def execute_command(self, command: Command, *, track_undo: bool = True) -> bool:
        """
        Execute a command instance directly.

        Args:
            command (Command): Command instance to execute
            track_undo (bool): When False, forces this specific call off the
                undo stack regardless of the command class's own
                occupies_undo_slot() default -- use for an automated/background
                trigger of a command that IS normally undo-tracked from other
                call sites. Does NOT affect whether the redo stack is
                cleared: a command that occupies_undo_slot() still
                invalidates any stale redo-stack entry by actually changing
                project state, whether or not this particular execution is
                itself undo-tracked.

        Returns:
            bool: True if command executed successfully
        """
        command_name = command.__class__.__name__
        self.logger.debug("Executing command: %s", command_name)

        try:
            result = command.execute()
            self._warn_if_not_command_result(result, command_name, "execute")

            if result is CommandResult.NOOP:
                self.logger.debug("Command execution was a no-op: %s", command_name)
                return False

            if result is CommandResult.FAILURE:
                self.logger.warning("Command execution failed: %s", command_name)
                return False

            if command.occupies_undo_slot():
                if track_undo:
                    self.undo_stack.append(command)
                    if len(self.undo_stack) > self.max_undo_levels:
                        removed_command = self.undo_stack.pop(0)
                        self._safe_cleanup(removed_command)
                        self.logger.debug("Removed old command from undo stack: %s", removed_command.__class__.__name__)

                # Clear redo stack since we executed a new command -- even
                # one not itself pushed onto the undo stack (track_undo=False)
                # still changed project state, so a stale redo-stack entry
                # recorded before it may no longer be valid to replay.
                if self.redo_stack:
                    self.logger.debug("Clearing redo stack (%d commands) due to new command execution", len(self.redo_stack))
                    for stale_command in self.redo_stack:
                        self._safe_cleanup(stale_command)
                    self.redo_stack.clear()

            self._notify_project_modified(command)
            self.logger.info("Successfully executed command: %s", command_name)
            self._notify_history_changed()
            return True
            
        except Exception as e:
            self.logger.error("Error executing command '%s': %s", 
                            command.__class__.__name__, str(e), exc_info=True)
            self.logger.debug("Command execution failed for: %s", repr(command))
            return False
    
    def undo(self) -> bool:
        """
        Undo the last command.
        
        Returns:
            bool: True if undo was successful
        """
        if not self.undo_stack:
            self.logger.debug("Undo requested but no commands in undo stack")
            return False
            
        command = self.undo_stack.pop()
        command_name = command.__class__.__name__
        self.logger.debug("Undoing command: %s", command_name)

        try:
            result = command.undo()
        except Exception as e:
            # command.undo() may have raised after partially mutating shared
            # project state, so it isn't safe to assume a retry would
            # succeed (or even be a no-op), nor that any other stack entry
            # is still valid -- see _invalidate_history_after_failure.
            self.logger.error("Error undoing command '%s': %s", command_name, str(e), exc_info=True)
            command_description = self._safe_display_name(command)
            self._notify_project_modified(command)
            self._invalidate_history_after_failure(command)
            self._notify_undo_redo_error(command_description, "undo")
            self._notify_history_changed()
            return False

        self._warn_if_not_command_result(result, command_name, "undo")

        if result is CommandResult.ABORTED:
            # Nothing happened -- put it back exactly where it was, don't
            # touch the redo stack or notify project-modified.
            self.undo_stack.append(command)
            self.logger.debug("Command undo aborted (no changes made): %s", command_name)
            self._notify_history_changed()
            return False

        self.redo_stack.append(command)
        if result is CommandResult.FAILURE:
            self.logger.warning("Command undo reported failure: %s", command_name)
        elif result is CommandResult.NOOP:
            self.logger.debug("Command undo was a no-op: %s", command_name)
        else:
            self._notify_project_modified(command)
            self.logger.info("Successfully undid command: %s", command_name)
        self._notify_history_changed()
        return True
    
    def redo(self) -> bool:
        """
        Redo the last undone command.
        
        Returns:
            bool: True if redo was successful
        """
        if not self.redo_stack:
            self.logger.debug("Redo requested but no commands in redo stack")
            return False
            
        command = self.redo_stack.pop()
        command_name = command.__class__.__name__
        self.logger.debug("Redoing command: %s", command_name)

        try:
            result = command.redo()
        except Exception as e:
            self.logger.error("Error redoing command '%s': %s", command_name, str(e), exc_info=True)
            command_description = self._safe_display_name(command)
            self._notify_project_modified(command)
            self._invalidate_history_after_failure(command)
            self._notify_undo_redo_error(command_description, "redo")
            self._notify_history_changed()
            return False

        self._warn_if_not_command_result(result, command_name, "redo")

        if result is CommandResult.ABORTED:
            # Nothing happened -- put it back exactly where it was, don't
            # touch the undo stack or notify project-modified.
            self.redo_stack.append(command)
            self.logger.debug("Command redo aborted (no changes made): %s", command_name)
            self._notify_history_changed()
            return False

        self.undo_stack.append(command)
        if result is CommandResult.FAILURE:
            self.logger.warning("Command redo reported failure: %s", command_name)
        elif result is CommandResult.NOOP:
            self.logger.debug("Command redo was a no-op: %s", command_name)
        else:
            self._notify_project_modified(command)
            self.logger.info("Successfully redid command: %s", command_name)
        self._notify_history_changed()
        return True
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self.redo_stack) > 0
    
    def get_undo_description(self) -> Optional[str]:
        """Get description of the command that would be undone."""
        if self.undo_stack:
            return str(self.undo_stack[-1])
        return None
    
    def get_redo_description(self) -> Optional[str]:
        """Get description of the command that would be redone."""
        if self.redo_stack:
            return str(self.redo_stack[-1])
        return None
    
    def clear_history(self):
        """Clear undo/redo history."""
        for command in self.undo_stack:
            self._safe_cleanup(command)
        for command in self.redo_stack:
            self._safe_cleanup(command)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._notify_history_changed()

    def _invalidate_history_after_failure(self, failed_command: Command) -> None:
        """A command's undo()/redo() raising leaves the shared project state
        in an unknown, possibly partially-mutated shape -- commands here
        operate on live shared objects (e.g. a Dataset's DataFrame, a
        Chart's series list), not isolated snapshots, so any other stack
        entry may have been recorded against an assumption about that state
        which no longer holds. The entire history is therefore dropped and
        cleaned up, not just the command that raised."""
        self._safe_cleanup(failed_command)
        for command in self.undo_stack:
            self._safe_cleanup(command)
        for command in self.redo_stack:
            self._safe_cleanup(command)
        self.undo_stack.clear()
        self.redo_stack.clear()

    def _safe_cleanup(self, command: Command) -> None:
        """Call command.cleanup(), isolating any exception it raises so it
        can never corrupt the caller's own control flow (e.g. turning an
        otherwise-successful execute_command() into a reported failure, or
        aborting a stack-clearing loop partway through)."""
        try:
            command.cleanup()
        except Exception as e:
            self.logger.error(
                "Error cleaning up command '%s': %s",
                command.__class__.__name__, str(e), exc_info=True)
