import logging
from pandaplot.commands.base_command import Command
from typing import List, Optional

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
        try:
            command.execute()
            
            # Add to undo stack
            self.undo_stack.append(command)
            if len(self.undo_stack) > self.max_undo_levels:
                #TODO: ensure we clean command references properly
                self.undo_stack.pop(0)
                
            # Clear redo stack since we executed a new command
            self.redo_stack.clear()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing command '{command.__class__.__name__}': {str(e)}")
            return False
    
    def undo(self) -> bool:
        """
        Undo the last command.
        
        Returns:
            bool: True if undo was successful
        """
        if not self.undo_stack:
            return False
            
        try:
            command = self.undo_stack.pop()
            command.undo()
            self.redo_stack.append(command)
            return True
            
        except Exception as e:
            self.logger.error(f"Error undoing command: {str(e)}")
            return False
    
    def redo(self) -> bool:
        """
        Redo the last undone command.
        
        Returns:
            bool: True if redo was successful
        """
        if not self.redo_stack:
            return False
            
        try:
            command = self.redo_stack.pop()
            command.redo()
            self.undo_stack.append(command)
            return True
            
        except Exception as e:
            self.logger.error(f"Error redoing command: {str(e)}")
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