from abc import ABC

import pytest

from pandaplot.commands.base_command import Command


class TestCommand:
    """Test cases for the abstract Command base class."""
    
    def test_command_is_abstract(self):
        """Test that Command is an abstract base class."""
        assert issubclass(Command, ABC)
        
        # Cannot instantiate abstract class directly
        with pytest.raises(TypeError):
            Command()
    
    def test_command_has_required_abstract_methods(self):
        """Test that Command defines the required abstract methods."""
        # Check that abstract methods are defined
        assert hasattr(Command, "execute")
        assert hasattr(Command, "undo")
        assert hasattr(Command, "redo")
        
        # Check that they are abstract methods
        assert Command.execute.__isabstractmethod__
        assert Command.undo.__isabstractmethod__
        assert Command.redo.__isabstractmethod__
    
    def test_command_repr_method(self):
        """Test that Command has a __repr__ method."""
        assert hasattr(Command, "__repr__")
        # The __repr__ method should not be abstract
        assert not getattr(Command.__repr__, "__isabstractmethod__", False)


class ConcreteCommand(Command):
    """Concrete implementation of Command for testing."""
    
    def __init__(self, name="TestCommand"):
        self.name = name
        self.executed = False
        self.undone = False
        self.redone = False
        self.execute_count = 0
        self.undo_count = 0
        self.redo_count = 0
    
    def execute(self):
        self.executed = True
        self.execute_count += 1
    
    def undo(self):
        self.undone = True
        self.undo_count += 1
    
    def redo(self):
        self.redone = True
        self.redo_count += 1
    
    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"


class FailingCommand(Command):
    """Command that fails for testing error handling."""
    
    def __init__(self, fail_on="execute"):
        self.fail_on = fail_on
    
    def execute(self):
        if self.fail_on == "execute":
            raise RuntimeError("Execute failed")
    
    def undo(self):
        if self.fail_on == "undo":
            raise RuntimeError("Undo failed")
    
    def redo(self):
        if self.fail_on == "redo":
            raise RuntimeError("Redo failed")


class TestConcreteCommand:
    """Test cases for concrete Command implementations."""
    
    def test_concrete_command_instantiation(self):
        """Test that concrete commands can be instantiated."""
        cmd = ConcreteCommand()
        assert isinstance(cmd, Command)
        assert cmd.name == "TestCommand"
        assert not cmd.executed
        assert not cmd.undone 
        assert not cmd.redone
    
    def test_concrete_command_with_custom_name(self):
        """Test concrete command with custom name."""
        cmd = ConcreteCommand("CustomCommand")
        assert cmd.name == "CustomCommand"
    
    def test_execute_method(self):
        """Test the execute method of concrete command."""
        cmd = ConcreteCommand()
        
        assert not cmd.executed
        assert cmd.execute_count == 0
        
        cmd.execute()
        
        assert cmd.executed
        assert cmd.execute_count == 1
    
    def test_undo_method(self):
        """Test the undo method of concrete command."""
        cmd = ConcreteCommand()
        
        assert not cmd.undone
        assert cmd.undo_count == 0
        
        cmd.undo()
        
        assert cmd.undone
        assert cmd.undo_count == 1
    
    def test_redo_method(self):
        """Test the redo method of concrete command."""
        cmd = ConcreteCommand()
        
        assert not cmd.redone
        assert cmd.redo_count == 0
        
        cmd.redo()
        
        assert cmd.redone
        assert cmd.redo_count == 1
    
    def test_multiple_executions(self):
        """Test that commands can be executed multiple times."""
        cmd = ConcreteCommand()
        
        cmd.execute()
        cmd.execute()
        cmd.execute()
        
        assert cmd.execute_count == 3
        
        cmd.undo()
        cmd.undo()
        
        assert cmd.undo_count == 2
        
        cmd.redo()
        
        assert cmd.redo_count == 1
    
    def test_command_repr(self):
        """Test the __repr__ method of Command."""
        cmd = ConcreteCommand("TestRepr")
        expected = "ConcreteCommand(name='TestRepr')"
        assert repr(cmd) == expected
    
    def test_command_default_repr(self):
        """Test the default __repr__ method from base Command."""
        cmd = ConcreteCommand()
        # Should use the base class __repr__ if not overridden
        # But our ConcreteCommand does override it
        assert "ConcreteCommand" in repr(cmd)
    
    def test_inheritance_hierarchy(self):
        """Test that concrete commands properly inherit from Command."""
        cmd = ConcreteCommand()
        
        assert isinstance(cmd, Command)
        assert isinstance(cmd, ABC)
        assert issubclass(ConcreteCommand, Command)
        assert issubclass(ConcreteCommand, ABC)


class TestCommandWithExceptions:
    """Test cases for commands that raise exceptions."""
    
    def test_failing_execute_command(self):
        """Test command that fails during execute."""
        cmd = FailingCommand("execute")
        
        with pytest.raises(RuntimeError, match="Execute failed"):
            cmd.execute()
    
    def test_failing_undo_command(self):
        """Test command that fails during undo."""
        cmd = FailingCommand("undo")
        
        with pytest.raises(RuntimeError, match="Undo failed"):
            cmd.undo()
    
    def test_failing_redo_command(self):
        """Test command that fails during redo."""
        cmd = FailingCommand("redo")
        
        with pytest.raises(RuntimeError, match="Redo failed"):
            cmd.redo()
    
    def test_partial_failure_scenarios(self):
        """Test commands that fail only on specific operations."""
        # Command that only fails on undo
        cmd1 = FailingCommand("undo")
        cmd1.execute()  # Should succeed
        
        with pytest.raises(RuntimeError):
            cmd1.undo()
        
        # Command that only fails on redo
        cmd2 = FailingCommand("redo")
        cmd2.execute()  # Should succeed
        cmd2.undo()     # Should succeed
        
        with pytest.raises(RuntimeError):
            cmd2.redo()


class TestCommandEdgeCases:
    """Test edge cases and unusual scenarios."""
    
    def test_command_with_no_custom_repr(self):
        """Test command that uses the default __repr__ from base class."""
        
        class MinimalCommand(Command):
            def execute(self):
                pass
            
            def undo(self):
                pass
            
            def redo(self):
                pass
        
        cmd = MinimalCommand()
        expected = "MinimalCommand()"
        assert repr(cmd) == expected
    
    def test_command_state_persistence(self):
        """Test that command state persists across method calls."""
        cmd = ConcreteCommand("StateTest")
        
        # Initial state
        assert cmd.execute_count == 0
        assert cmd.undo_count == 0
        assert cmd.redo_count == 0
        
        # Execute and check state persistence
        cmd.execute()
        assert cmd.execute_count == 1
        assert cmd.executed
        
        # Undo and check state persistence
        cmd.undo()
        assert cmd.undo_count == 1
        assert cmd.undone
        assert cmd.execute_count == 1  # Should still be 1
        
        # Redo and check state persistence
        cmd.redo()
        assert cmd.redo_count == 1
        assert cmd.redone
        assert cmd.execute_count == 1  # Should still be 1
        assert cmd.undo_count == 1     # Should still be 1
    
    def test_multiple_command_instances(self):
        """Test that multiple command instances maintain separate state."""
        cmd1 = ConcreteCommand("Command1")
        cmd2 = ConcreteCommand("Command2")
        
        cmd1.execute()
        assert cmd1.executed
        assert not cmd2.executed
        
        cmd2.undo()
        assert cmd1.execute_count == 1
        assert cmd1.undo_count == 0
        assert cmd2.execute_count == 0
        assert cmd2.undo_count == 1
    
    def test_command_method_chaining_compatibility(self):
        """Test that command methods can be called in sequence."""
        cmd = ConcreteCommand()
        
        # Should be able to call methods in any order
        cmd.execute()
        cmd.undo()
        cmd.redo()
        cmd.execute()
        cmd.undo()
        
        assert cmd.execute_count == 2
        assert cmd.undo_count == 2
        assert cmd.redo_count == 1
