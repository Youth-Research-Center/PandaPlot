import logging
from typing import Callable, List, Optional

from pandaplot.commands.base_command import Command


class CommandExecutor:
    """
    Command executor that manages command execution, undo/redo functionality.
    This is the central point for executing commands.
    """

    def __init__(self, on_history_changed: Optional[Callable[[], None]] = None):
        self.logger = logging.getLogger(self.__class__.__name__)

        # Undo/Redo functionality
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.max_undo_levels = 10

        # Optional hook invoked whenever can_undo()/can_redo() may have
        # changed (a command executed, was undone/redone, or history was
        # cleared) -- wired by app.py to emit AppEvents.HISTORY_CHANGED, so
        # e.g. the Edit menu's Undo/Redo actions can keep their enabled
        # state in sync without polling.
        self.on_history_changed = on_history_changed

    def _notify_history_changed(self) -> None:
        if self.on_history_changed:
            self.on_history_changed()

    def execute_command(self, command: Command, *, track_undo: bool = True) -> bool:
        """
        Execute a command instance directly.

        Args:
            command (Command): Command instance to execute
            track_undo (bool): When False, forces this specific call off the
                undo stack regardless of the command class's own
                occupies_undo_slot() default -- use for an automated/background
                trigger of a command that IS normally undo-tracked from other
                call sites (e.g. an autosave tick invoking SaveProjectCommand,
                which must still occupy an undo slot for the manual Save menu
                action).

        Returns:
            bool: True if command executed successfully
        """
        command_name = command.__class__.__name__
        self.logger.debug("Executing command: %s", command_name)

        try:
            success = command.execute()

            if success is False:
                self.logger.warning("Command execution failed: %s", command_name)
                return False

            if track_undo and command.occupies_undo_slot():
                self.undo_stack.append(command)
                if len(self.undo_stack) > self.max_undo_levels:
                    removed_command = self.undo_stack.pop(0)
                    self._safe_cleanup(removed_command)
                    self.logger.debug("Removed old command from undo stack: %s", removed_command.__class__.__name__)

                # Clear redo stack since we executed a new command
                if self.redo_stack:
                    self.logger.debug("Clearing redo stack (%d commands) due to new command execution", len(self.redo_stack))
                    for stale_command in self.redo_stack:
                        self._safe_cleanup(stale_command)
                    self.redo_stack.clear()

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
            
        command = self.undo_stack[-1]  # Peek at the command
        command_name = command.__class__.__name__
        self.logger.debug("Undoing command: %s", command_name)
        
        try:
            command = self.undo_stack.pop()
            command.undo()
            self.redo_stack.append(command)
            self.logger.info("Successfully undid command: %s", command_name)
            self._notify_history_changed()
            return True
            
        except Exception as e:
            self.logger.error("Error undoing command '%s': %s", 
                            command.__class__.__name__ if command else "Unknown", str(e), exc_info=True)
            self.logger.debug("Undo operation failed for command: %s", repr(command) if command else "None")
            return False
    
    def redo(self) -> bool:
        """
        Redo the last undone command.
        
        Returns:
            bool: True if redo was successful
        """
        if not self.redo_stack:
            self.logger.debug("Redo requested but no commands in redo stack")
            return False
            
        command = self.redo_stack[-1]  # Peek at the command
        command_name = command.__class__.__name__
        self.logger.debug("Redoing command: %s", command_name)
        
        try:
            command = self.redo_stack.pop()
            command.redo()
            self.undo_stack.append(command)
            self.logger.info("Successfully redid command: %s", command_name)
            self._notify_history_changed()
            return True
            
        except Exception as e:
            self.logger.error("Error redoing command '%s': %s", 
                            command.__class__.__name__ if command else "Unknown", str(e), exc_info=True)
            self.logger.debug("Redo operation failed for command: %s", repr(command) if command else "None")
            return False
    
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
