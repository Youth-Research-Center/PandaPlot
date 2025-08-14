import logging
from typing import List, Optional

from pandaplot.commands.base_command import Command


class CommandExecutor:
    """
    Command executor that manages command execution, undo/redo functionality.
    This is the central point for executing commands in the MVC architecture.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Undo/Redo functionality
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.max_undo_levels = 10
    
    def execute_command(self, command: Command) -> bool:
        """
        Execute a command instance directly.
        
        Args:
            command (Command): Command instance to execute
            
        Returns:
            bool: True if command executed successfully
        """
        command_name = command.__class__.__name__
        self.logger.debug("Executing command: %s", command_name)
        
        try:
            command.execute()
            
            # Add to undo stack
            self.undo_stack.append(command)
            if len(self.undo_stack) > self.max_undo_levels:
                #TODO: ensure we clean command references properly
                removed_command = self.undo_stack.pop(0)
                self.logger.debug("Removed old command from undo stack: %s", removed_command.__class__.__name__)
                
            # Clear redo stack since we executed a new command
            if self.redo_stack:
                self.logger.debug("Clearing redo stack (%d commands) due to new command execution", len(self.redo_stack))
                self.redo_stack.clear()
            
            self.logger.info("Successfully executed command: %s", command_name)
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
        self.undo_stack.clear()
        self.redo_stack.clear()