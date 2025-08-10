from unittest.mock import patch
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.base_command import Command


class MockCommand(Command):
    """Mock command for testing."""
    
    def __init__(self, name="MockCommand", should_fail=False, fail_on=None):
        self.name = name
        self.should_fail = should_fail
        self.fail_on = fail_on
        self.executed = False
        self.undone = False
        self.redone = False
        self.execute_count = 0
        self.undo_count = 0
        self.redo_count = 0
    
    def execute(self):
        if self.should_fail and self.fail_on == "execute":
            raise RuntimeError(f"{self.name} execute failed")
        self.executed = True
        self.execute_count += 1
    
    def undo(self):
        if self.should_fail and self.fail_on == "undo":
            raise RuntimeError(f"{self.name} undo failed")
        self.undone = True
        self.undo_count += 1
    
    def redo(self):
        if self.should_fail and self.fail_on == "redo":
            raise RuntimeError(f"{self.name} redo failed")
        self.redone = True
        self.redo_count += 1
    
    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"


class TestCommandExecutor:
    """Test cases for CommandExecutor initialization and basic properties."""
    
    def test_executor_initialization(self):
        """Test CommandExecutor initialization with default values."""
        executor = CommandExecutor()
        
        assert isinstance(executor.undo_stack, list)
        assert isinstance(executor.redo_stack, list)
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
        assert executor.max_undo_levels == 10
    
    def test_executor_initial_state(self):
        """Test initial state of CommandExecutor."""
        executor = CommandExecutor()
        
        assert not executor.can_undo()
        assert not executor.can_redo()
        assert executor.get_undo_description() is None
        assert executor.get_redo_description() is None


class TestCommandExecution:
    """Test cases for command execution."""
    
    def test_execute_command_success(self):
        """Test successful command execution."""
        executor = CommandExecutor()
        command = MockCommand("TestCommand")
        
        result = executor.execute_command(command)
        
        assert result is True
        assert command.executed
        assert command.execute_count == 1
        assert len(executor.undo_stack) == 1
        assert executor.undo_stack[0] is command
        assert len(executor.redo_stack) == 0
    
    def test_execute_command_failure(self):
        """Test command execution that fails."""
        executor = CommandExecutor()
        command = MockCommand("FailingCommand", should_fail=True, fail_on="execute")
        
        result = executor.execute_command(command)
        
        assert result is False
        assert not command.executed
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
    
    def test_execute_multiple_commands(self):
        """Test executing multiple commands."""
        executor = CommandExecutor()
        cmd1 = MockCommand("Command1")
        cmd2 = MockCommand("Command2")
        cmd3 = MockCommand("Command3")
        
        executor.execute_command(cmd1)
        executor.execute_command(cmd2)
        executor.execute_command(cmd3)
        
        assert len(executor.undo_stack) == 3
        assert executor.undo_stack[0] is cmd1
        assert executor.undo_stack[1] is cmd2
        assert executor.undo_stack[2] is cmd3
        assert len(executor.redo_stack) == 0
    
    def test_execute_command_clears_redo_stack(self):
        """Test that executing a new command clears the redo stack."""
        executor = CommandExecutor()
        cmd1 = MockCommand("Command1")
        cmd2 = MockCommand("Command2")
        
        # Execute and undo command to populate redo stack
        executor.execute_command(cmd1)
        executor.undo()
        assert len(executor.redo_stack) == 1
        
        # Execute new command should clear redo stack
        executor.execute_command(cmd2)
        assert len(executor.redo_stack) == 0
        assert len(executor.undo_stack) == 1
        assert executor.undo_stack[0] is cmd2


class TestUndoFunctionality:
    """Test cases for undo functionality."""
    
    def test_undo_success(self):
        """Test successful undo operation."""
        executor = CommandExecutor()
        command = MockCommand("TestCommand")
        
        executor.execute_command(command)
        result = executor.undo()
        
        assert result is True
        assert command.undone
        assert command.undo_count == 1
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 1
        assert executor.redo_stack[0] is command
    
    def test_undo_empty_stack(self):
        """Test undo when undo stack is empty."""
        executor = CommandExecutor()
        
        result = executor.undo()
        
        assert result is False
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
    
    def test_undo_failure(self):
        """Test undo operation that fails."""
        executor = CommandExecutor()
        command = MockCommand("FailingCommand", should_fail=True, fail_on="undo")
        
        executor.execute_command(command)
        
        result = executor.undo()
        
        assert result is False
        # Command should be removed from undo stack even if undo fails
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
    
    def test_multiple_undo_operations(self):
        """Test multiple undo operations."""
        executor = CommandExecutor()
        cmd1 = MockCommand("Command1")
        cmd2 = MockCommand("Command2")
        cmd3 = MockCommand("Command3")
        
        executor.execute_command(cmd1)
        executor.execute_command(cmd2)
        executor.execute_command(cmd3)
        
        # Undo all commands
        result1 = executor.undo()  # Undo cmd3
        result2 = executor.undo()  # Undo cmd2
        result3 = executor.undo()  # Undo cmd1
        
        assert all([result1, result2, result3])
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 3
        assert executor.redo_stack[0] is cmd3
        assert executor.redo_stack[1] is cmd2
        assert executor.redo_stack[2] is cmd1


class TestRedoFunctionality:
    """Test cases for redo functionality."""
    
    def test_redo_success(self):
        """Test successful redo operation."""
        executor = CommandExecutor()
        command = MockCommand("TestCommand")
        
        executor.execute_command(command)
        executor.undo()
        result = executor.redo()
        
        assert result is True
        assert command.redone
        assert command.redo_count == 1
        assert len(executor.undo_stack) == 1
        assert len(executor.redo_stack) == 0
        assert executor.undo_stack[0] is command
    
    def test_redo_empty_stack(self):
        """Test redo when redo stack is empty."""
        executor = CommandExecutor()
        
        result = executor.redo()
        
        assert result is False
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
    
    def test_redo_failure(self):
        """Test redo operation that fails."""
        executor = CommandExecutor()
        command = MockCommand("FailingCommand", should_fail=True, fail_on="redo")
        
        executor.execute_command(command)
        executor.undo()
        
        result = executor.redo()
        
        assert result is False
        # Command should be removed from redo stack even if redo fails
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
    
    def test_multiple_redo_operations(self):
        """Test multiple redo operations."""
        executor = CommandExecutor()
        cmd1 = MockCommand("Command1")
        cmd2 = MockCommand("Command2")
        cmd3 = MockCommand("Command3")
        
        # Execute and undo all commands
        executor.execute_command(cmd1)
        executor.execute_command(cmd2)
        executor.execute_command(cmd3)
        executor.undo()
        executor.undo()
        executor.undo()
        
        # Redo all commands
        result1 = executor.redo()  # Redo cmd1
        result2 = executor.redo()  # Redo cmd2
        result3 = executor.redo()  # Redo cmd3
        
        assert all([result1, result2, result3])
        assert len(executor.undo_stack) == 3
        assert len(executor.redo_stack) == 0
        assert executor.undo_stack[0] is cmd1
        assert executor.undo_stack[1] is cmd2
        assert executor.undo_stack[2] is cmd3


class TestCanUndoRedo:
    """Test cases for can_undo and can_redo methods."""
    
    def test_can_undo_with_commands(self):
        """Test can_undo when commands are available."""
        executor = CommandExecutor()
        command = MockCommand("TestCommand")
        
        assert not executor.can_undo()
        
        executor.execute_command(command)
        assert executor.can_undo()
        
        executor.undo()
        assert not executor.can_undo()
    
    def test_can_redo_with_commands(self):
        """Test can_redo when commands are available."""
        executor = CommandExecutor()
        command = MockCommand("TestCommand")
        
        assert not executor.can_redo()
        
        executor.execute_command(command)
        assert not executor.can_redo()
        
        executor.undo()
        assert executor.can_redo()
        
        executor.redo()
        assert not executor.can_redo()
    
    def test_can_undo_redo_state_consistency(self):
        """Test that can_undo and can_redo reflect actual stack states."""
        executor = CommandExecutor()
        cmd1 = MockCommand("Command1")
        cmd2 = MockCommand("Command2")
        
        # Initial state
        assert not executor.can_undo()
        assert not executor.can_redo()
        
        # After execute
        executor.execute_command(cmd1)
        assert executor.can_undo()
        assert not executor.can_redo()
        
        # After another execute
        executor.execute_command(cmd2)
        assert executor.can_undo()
        assert not executor.can_redo()
        
        # After undo
        executor.undo()
        assert executor.can_undo()
        assert executor.can_redo()
        
        # After another undo
        executor.undo()
        assert not executor.can_undo()
        assert executor.can_redo()


class TestDescriptionMethods:
    """Test cases for get_undo_description and get_redo_description."""
    
    def test_get_undo_description_with_commands(self):
        """Test get_undo_description when commands are available."""
        executor = CommandExecutor()
        command = MockCommand("TestCommand")
        
        assert executor.get_undo_description() is None
        
        executor.execute_command(command)
        description = executor.get_undo_description()
        assert description == "MockCommand(name='TestCommand')"
        
        executor.undo()
        assert executor.get_undo_description() is None
    
    def test_get_redo_description_with_commands(self):
        """Test get_redo_description when commands are available."""
        executor = CommandExecutor()
        command = MockCommand("TestCommand")
        
        assert executor.get_redo_description() is None
        
        executor.execute_command(command)
        assert executor.get_redo_description() is None
        
        executor.undo()
        description = executor.get_redo_description()
        assert description == "MockCommand(name='TestCommand')"
        
        executor.redo()
        assert executor.get_redo_description() is None
    
    def test_description_methods_with_multiple_commands(self):
        """Test description methods with multiple commands."""
        executor = CommandExecutor()
        cmd1 = MockCommand("Command1")
        cmd2 = MockCommand("Command2")
        cmd3 = MockCommand("Command3")
        
        executor.execute_command(cmd1)
        executor.execute_command(cmd2)
        executor.execute_command(cmd3)
        
        # Should return description of last command
        assert executor.get_undo_description() == "MockCommand(name='Command3')"
        
        executor.undo()
        assert executor.get_undo_description() == "MockCommand(name='Command2')"
        assert executor.get_redo_description() == "MockCommand(name='Command3')"
        
        executor.undo()
        assert executor.get_undo_description() == "MockCommand(name='Command1')"
        assert executor.get_redo_description() == "MockCommand(name='Command2')"


class TestMaxUndoLevels:
    """Test cases for max undo levels functionality."""
    
    def test_max_undo_levels_enforcement(self):
        """Test that max undo levels are enforced."""
        executor = CommandExecutor()
        executor.max_undo_levels = 3
        
        # Execute more commands than max levels
        commands = [MockCommand(f"Command{i}") for i in range(5)]
        for cmd in commands:
            executor.execute_command(cmd)
        
        # Should only keep last 3 commands
        assert len(executor.undo_stack) == 3
        assert executor.undo_stack[0] is commands[2]  # Command2
        assert executor.undo_stack[1] is commands[3]  # Command3
        assert executor.undo_stack[2] is commands[4]  # Command4
    
    def test_max_undo_levels_zero(self):
        """Test behavior when max undo levels is 0."""
        executor = CommandExecutor()
        executor.max_undo_levels = 0
        
        command = MockCommand("TestCommand")
        executor.execute_command(command)
        
        # Should not keep any commands
        assert len(executor.undo_stack) == 0
        assert not executor.can_undo()
    
    def test_max_undo_levels_modification(self):
        """Test behavior when max undo levels is modified after commands."""
        executor = CommandExecutor()
        
        # Add some commands within normal max_undo_levels
        commands = [MockCommand(f"Command{i}") for i in range(3)]
        for cmd in commands:
            executor.execute_command(cmd)
        
        assert len(executor.undo_stack) == 3
        
        # Modify max levels to be lower
        executor.max_undo_levels = 2
        
        # The existing stack is not automatically trimmed
        assert len(executor.undo_stack) == 3
        
        # Add a new command - this will add to stack (4 total) then remove 1 (3 remaining)
        # The trimming logic only removes one element when size > max_undo_levels
        new_cmd = MockCommand("NewCommand")
        executor.execute_command(new_cmd)
        
        # Stack size should still be 3 (added 1, removed 1)
        assert len(executor.undo_stack) == 3
        assert executor.undo_stack[-1] is new_cmd
        
        # Verify that future commands will maintain the trimming behavior
        another_cmd = MockCommand("AnotherCommand")
        executor.execute_command(another_cmd)
        
        # Still 3 commands (one in, one out)
        assert len(executor.undo_stack) == 3
        assert executor.undo_stack[-1] is another_cmd


class TestClearHistory:
    """Test cases for clear_history functionality."""
    
    def test_clear_history_with_commands(self):
        """Test clearing history when commands exist."""
        executor = CommandExecutor()
        cmd1 = MockCommand("Command1")
        cmd2 = MockCommand("Command2")
        
        executor.execute_command(cmd1)
        executor.execute_command(cmd2)
        executor.undo()
        
        # Should have commands in both stacks
        assert len(executor.undo_stack) == 1
        assert len(executor.redo_stack) == 1
        
        executor.clear_history()
        
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
        assert not executor.can_undo()
        assert not executor.can_redo()
        assert executor.get_undo_description() is None
        assert executor.get_redo_description() is None
    
    def test_clear_history_empty_stacks(self):
        """Test clearing history when stacks are already empty."""
        executor = CommandExecutor()
        
        executor.clear_history()
        
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
        assert not executor.can_undo()
        assert not executor.can_redo()


class TestEdgeCases:
    """Test edge cases and complex scenarios."""
    
    def test_command_state_after_execution_failure(self):
        """Test command state when execution fails."""
        executor = CommandExecutor()
        command = MockCommand("FailingCommand", should_fail=True, fail_on="execute")
        
        with patch('builtins.print'):
            executor.execute_command(command)
        
        # Command should not be executed or added to stack
        assert not command.executed
        assert command.execute_count == 0
        assert len(executor.undo_stack) == 0
    
    def test_mixed_success_failure_commands(self):
        """Test mixing successful and failing commands."""
        executor = CommandExecutor()
        cmd1 = MockCommand("SuccessCommand1")
        cmd2 = MockCommand("FailingCommand", should_fail=True, fail_on="execute")
        cmd3 = MockCommand("SuccessCommand2")
        
        with patch('builtins.print'):
            result1 = executor.execute_command(cmd1)
            result2 = executor.execute_command(cmd2)
            result3 = executor.execute_command(cmd3)
        
        assert result1 is True
        assert result2 is False
        assert result3 is True
        
        # Only successful commands should be in stack
        assert len(executor.undo_stack) == 2
        assert executor.undo_stack[0] is cmd1
        assert executor.undo_stack[1] is cmd3
    
    def test_undo_redo_cycle_integrity(self):
        """Test that undo/redo cycles maintain integrity."""
        executor = CommandExecutor()
        command = MockCommand("CycleCommand")
        
        # Execute -> Undo -> Redo -> Undo -> Redo
        executor.execute_command(command)
        executor.undo()
        executor.redo()
        executor.undo()
        executor.redo()
        
        # Command should have correct counts
        assert command.execute_count == 1
        assert command.undo_count == 2
        assert command.redo_count == 2
        
        # Final state should be as if command is executed
        assert len(executor.undo_stack) == 1
        assert len(executor.redo_stack) == 0
        assert executor.can_undo()
        assert not executor.can_redo()
    
    def test_command_reference_integrity(self):
        """Test that command references are maintained correctly."""
        executor = CommandExecutor()
        command = MockCommand("ReferenceTest")
        
        executor.execute_command(command)
        
        # Get reference from undo stack
        undo_ref = executor.undo_stack[0]
        assert undo_ref is command
        
        executor.undo()
        
        # Get reference from redo stack
        redo_ref = executor.redo_stack[0]
        assert redo_ref is command
        assert redo_ref is undo_ref
        
        executor.redo()
        
        # Get reference from undo stack again
        undo_ref2 = executor.undo_stack[0]
        assert undo_ref2 is command
        assert undo_ref2 is undo_ref
        assert undo_ref2 is redo_ref
