"""
Unit tests for pandaplot.commands.app.exit_command module.

Tests cover the ExitCommand class, including:
- Command initialization
- Execute functionality and event emission
- Undo/Redo error handling (not applicable operations)
- Integration with AppContext and EventBus
- Base Command inheritance
- Edge cases and error conditions
"""

from unittest.mock import MagicMock, Mock, call

import pytest

from pandaplot.commands.app.exit_command import ExitCommand
from pandaplot.commands.base_command import Command
from pandaplot.models.events import AppEvents
from pandaplot.models.state.app_context import AppContext


# Fixtures
@pytest.fixture
def mock_event_bus():
    """Create a mock EventBus for testing."""
    mock_bus = Mock()
    mock_bus.emit = Mock()
    return mock_bus


@pytest.fixture
def mock_app_state():
    """Create a mock AppState for testing."""
    return Mock()


@pytest.fixture
def mock_command_executor():
    """Create a mock CommandExecutor for testing."""
    return Mock()


@pytest.fixture
def mock_ui_controller():
    """Create a mock UIController for testing."""
    return Mock()


@pytest.fixture
def mock_app_context(mock_app_state, mock_event_bus, mock_command_executor, mock_ui_controller):
    """Create a mock AppContext with all dependencies."""
    context = Mock(spec=AppContext)
    context.app_state = mock_app_state
    context.event_bus = mock_event_bus
    context.command_executor = mock_command_executor
    context.ui_controller = mock_ui_controller
    return context


@pytest.fixture
def exit_command(mock_app_context):
    """Create an ExitCommand instance for testing."""
    return ExitCommand(mock_app_context)


class TestExitCommandInitialization:
    """Test ExitCommand initialization and basic properties."""
    
    def test_initialization_with_app_context(self, mock_app_context):
        """Test ExitCommand initialization with AppContext."""
        command = ExitCommand(mock_app_context)
        
        assert command.app_context == mock_app_context
        assert isinstance(command, Command)
        assert isinstance(command, ExitCommand)
    
    def test_initialization_stores_app_context_reference(self, mock_app_context):
        """Test that initialization properly stores the AppContext reference."""
        command = ExitCommand(mock_app_context)
        
        # Verify the app_context is stored correctly
        assert command.app_context is mock_app_context
        assert hasattr(command, "app_context")


class TestExitCommandExecution:
    """Test ExitCommand execute functionality."""
    
    def test_execute_emits_app_exit_event(self, exit_command, mock_app_context):
        """Test that execute emits the 'app_exit' event."""
        exit_command.execute()
        
        # Verify that the event bus emit method was called with 'app_exit'
        mock_app_context.event_bus.emit.assert_called_once_with(AppEvents.APP_CLOSING)
    
    def test_execute_multiple_calls(self, exit_command, mock_app_context):
        """Test multiple execute calls."""
        exit_command.execute()
        exit_command.execute()
        exit_command.execute()
        
        # Verify emit was called three times
        assert mock_app_context.event_bus.emit.call_count == 3
        
        # Verify all calls were with 'app_exit'
        expected_calls = [call(AppEvents.APP_CLOSING), call(AppEvents.APP_CLOSING), call(AppEvents.APP_CLOSING)]
        mock_app_context.event_bus.emit.assert_has_calls(expected_calls)
    
    def test_execute_with_different_event_bus_states(self, mock_app_context):
        """Test execute works regardless of event bus state."""
        # Test with different mock behaviors
        scenarios = [
            Mock(),  # Normal mock
            Mock(side_effect=lambda x: None),  # Mock with side effect
            MagicMock(),  # MagicMock
        ]
        
        for mock_event_bus in scenarios:
            mock_app_context.event_bus = mock_event_bus
            command = ExitCommand(mock_app_context)
            
            # Should not raise any exceptions
            command.execute()
            mock_event_bus.emit.assert_called_with(AppEvents.APP_CLOSING)


class TestExitCommandUndoRedo:
    """Test ExitCommand undo and redo functionality."""
    
    def test_undo_raises_not_implemented_error(self, exit_command):
        """Test that undo raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Exit command cannot be undone"):
            exit_command.undo()
    
    def test_redo_raises_not_implemented_error(self, exit_command):
        """Test that redo raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Exit command cannot be redone"):
            exit_command.redo()
    
    def test_undo_error_message(self, exit_command):
        """Test that undo error message is correct."""
        try:
            exit_command.undo()
            pytest.fail("Expected NotImplementedError")
        except NotImplementedError as e:
            assert str(e) == "Exit command cannot be undone."
    
    def test_redo_error_message(self, exit_command):
        """Test that redo error message is correct."""
        try:
            exit_command.redo()
            pytest.fail("Expected NotImplementedError")
        except NotImplementedError as e:
            assert str(e) == "Exit command cannot be redone."


class TestExitCommandInheritance:
    """Test ExitCommand inheritance from base Command."""
    
    def test_is_instance_of_command(self, exit_command):
        """Test that ExitCommand is an instance of Command."""
        assert isinstance(exit_command, Command)
    
    def test_implements_command_interface(self, exit_command):
        """Test that ExitCommand implements the Command interface."""
        # All abstract methods should be implemented
        assert hasattr(exit_command, "execute")
        assert hasattr(exit_command, "undo")
        assert hasattr(exit_command, "redo")
        assert callable(exit_command.execute)
        assert callable(exit_command.undo)
        assert callable(exit_command.redo)
    
    def test_repr_method_inherited(self, exit_command):
        """Test that __repr__ method works correctly."""
        repr_str = repr(exit_command)
        assert "ExitCommand" in repr_str
        assert repr_str == "ExitCommand()"


class TestExitCommandIntegration:
    """Test ExitCommand integration scenarios."""
    
    def test_execute_after_failed_undo(self, exit_command, mock_app_context):
        """Test that execute still works after a failed undo attempt."""
        # Try to undo (should fail)
        with pytest.raises(NotImplementedError):
            exit_command.undo()
        
        # Execute should still work
        exit_command.execute()
        mock_app_context.event_bus.emit.assert_called_once_with(AppEvents.APP_CLOSING)

    def test_execute_after_failed_redo(self, exit_command, mock_app_context):
        """Test that execute still works after a failed redo attempt."""
        # Try to redo (should fail)
        with pytest.raises(NotImplementedError):
            exit_command.redo()
        
        # Execute should still work
        exit_command.execute()
        mock_app_context.event_bus.emit.assert_called_once_with(AppEvents.APP_CLOSING)
    
    def test_multiple_operations_sequence(self, exit_command, mock_app_context):
        """Test a sequence of operations including failures."""
        # Execute first
        exit_command.execute()
        
        # Try to undo (should fail)
        with pytest.raises(NotImplementedError):
            exit_command.undo()
        
        # Execute again
        exit_command.execute()
        
        # Try to redo (should fail)
        with pytest.raises(NotImplementedError):
            exit_command.redo()
        
        # Execute one more time
        exit_command.execute()
        
        # Verify execute was called 3 times total
        assert mock_app_context.event_bus.emit.call_count == 3
        expected_calls = [call(AppEvents.APP_CLOSING)] * 3
        mock_app_context.event_bus.emit.assert_has_calls(expected_calls)


class TestExitCommandEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_initialization_with_none_app_context(self):
        """Test initialization with None as app_context."""
        # This should work during initialization
        command = ExitCommand(None) # type: ignore
        assert command.app_context is None
        
        # But execute should fail when trying to access event_bus
        with pytest.raises(AttributeError):
            command.execute()
    
    def test_app_context_without_event_bus(self):
        """Test with AppContext that doesn't have event_bus."""
        mock_context = Mock()
        # Don't set event_bus attribute
        delattr(mock_context, "event_bus") if hasattr(mock_context, "event_bus") else None
        
        command = ExitCommand(mock_context)
        
        with pytest.raises(AttributeError):
            command.execute()
    
    def test_event_bus_without_emit_method(self, mock_app_context):
        """Test with event bus that doesn't have emit method."""
        mock_app_context.event_bus = Mock()
        delattr(mock_app_context.event_bus, "emit")
        
        command = ExitCommand(mock_app_context)
        
        with pytest.raises(AttributeError):
            command.execute()
    
    def test_event_bus_emit_raises_exception(self, mock_app_context):
        """Test behavior when event_bus.emit raises an exception."""
        mock_app_context.event_bus.emit.side_effect = RuntimeError("Event bus error")
        
        command = ExitCommand(mock_app_context)
        
        # The exception should propagate
        with pytest.raises(RuntimeError, match="Event bus error"):
            command.execute()
    
    def test_command_state_after_initialization(self, exit_command):
        """Test command state immediately after initialization."""
        # Should be able to call execute without any prior operations
        assert hasattr(exit_command, "app_context")
        assert hasattr(exit_command, "execute")
        assert hasattr(exit_command, "undo")
        assert hasattr(exit_command, "redo")
    
    def test_command_immutability_of_app_context_reference(self, mock_app_context):
        """Test that the app_context reference doesn't change after initialization."""
        command = ExitCommand(mock_app_context)
        original_context = command.app_context
        
        # Execute command
        command.execute()
        
        # Context reference should remain the same
        assert command.app_context is original_context
        assert command.app_context is mock_app_context


class TestExitCommandDocumentation:
    """Test command documentation and metadata."""
    
    def test_class_docstring(self):
        """Test that the class has proper documentation."""
        assert ExitCommand.__doc__ is not None
        assert "Command to exit the application" in ExitCommand.__doc__
    
    def test_execute_method_docstring(self, exit_command):
        """Test that execute method has documentation."""
        assert exit_command.execute.__doc__ is not None
        assert "Execute the exit command" in exit_command.execute.__doc__
    
    def test_undo_method_docstring(self, exit_command):
        """Test that undo method has documentation."""
        assert exit_command.undo.__doc__ is not None
        assert "not applicable" in exit_command.undo.__doc__.lower()
    
    def test_redo_method_docstring(self, exit_command):
        """Test that redo method has documentation."""
        assert exit_command.redo.__doc__ is not None
        assert "not applicable" in exit_command.redo.__doc__.lower()


if __name__ == "__main__":
    pytest.main([__file__])
