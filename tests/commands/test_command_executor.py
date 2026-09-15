from unittest.mock import patch

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.command_executor import CommandExecutor


class MockCommand(Command):
    """Mock command for testing."""

    def __init__(self, name="MockCommand", *, should_fail=False, fail_on=None):
        self.name = name
        self.should_fail = should_fail
        self.fail_on = fail_on
        self.executed = False
        self.undone = False
        self.redone = False
        self.execute_count = 0
        self.undo_count = 0
        self.redo_count = 0
        self.cleanup_count = 0

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

    def cleanup(self):
        self.cleanup_count += 1

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


class RaisingCleanupCommand(MockCommand):
    """A command whose cleanup() raises, to verify CommandExecutor isolates
    cleanup() failures from its own control flow (execute_command()'s return
    value, and the redo/undo-stack-clearing loops)."""

    def cleanup(self):
        self.cleanup_count += 1
        raise RuntimeError(f"{self.name} cleanup failed")


class StackExemptCommand(MockCommand):
    """A command that never occupies an undo/redo slot, e.g. a fire-and-forget
    dialog opener whose real effect happens later via its own execute_command()
    call (see CreateChartFromWizardCommand)."""

    def occupies_undo_slot(self):
        return False


class TestOccupiesUndoSlotOptOut:
    """Test cases for commands that opt out of the undo/redo stacks."""

    def test_stack_exempt_command_is_not_pushed_to_undo_stack(self):
        executor = CommandExecutor()
        command = StackExemptCommand("ExemptCommand")

        result = executor.execute_command(command)

        assert result is True
        assert command.executed
        assert len(executor.undo_stack) == 0
        assert not executor.can_undo()

    def test_stack_exempt_command_does_not_clear_redo_stack(self):
        """A stack-exempt command's execution must not wipe out redo history
        that a real, tracked command left behind."""
        executor = CommandExecutor()
        tracked = MockCommand("Tracked")
        executor.execute_command(tracked)
        executor.undo()
        assert len(executor.redo_stack) == 1

        exempt = StackExemptCommand("Exempt")
        executor.execute_command(exempt)

        assert len(executor.redo_stack) == 1
        assert executor.redo_stack[0] is tracked

    def test_stack_exempt_command_undo_redo_never_called_by_executor(self):
        executor = CommandExecutor()
        command = StackExemptCommand("Exempt")

        executor.execute_command(command)
        executor.undo()  # nothing on the stack to undo
        executor.redo()  # nothing on the stack to redo

        assert command.undo_count == 0
        assert command.redo_count == 0


class TestTrackUndoOptOut:
    """Test cases for the per-call track_undo=False opt-out of
    execute_command(), independent of the command class's own
    occupies_undo_slot() default."""

    def test_track_undo_false_does_not_push_normally_tracked_command(self):
        executor = CommandExecutor()
        command = MockCommand("TrackedButOptedOut")  # occupies_undo_slot() defaults to True

        result = executor.execute_command(command, track_undo=False)

        assert result is True
        assert command.executed
        assert len(executor.undo_stack) == 0
        assert not executor.can_undo()

    def test_default_track_undo_true_still_pushes_command(self):
        """Regression guard: the default behavior (track_undo=True) must be
        unchanged by the new parameter."""
        executor = CommandExecutor()
        command = MockCommand("DefaultTracked")

        result = executor.execute_command(command)

        assert result is True
        assert len(executor.undo_stack) == 1
        assert executor.undo_stack[0] is command

    def test_track_undo_false_on_stack_exempt_command_is_still_not_pushed(self):
        """Redundant-but-consistent case: a command that already opts itself
        out via occupies_undo_slot()==False stays off the stack when the
        caller also passes track_undo=False."""
        executor = CommandExecutor()
        command = StackExemptCommand("AlreadyExempt")

        result = executor.execute_command(command, track_undo=False)

        assert result is True
        assert len(executor.undo_stack) == 0

    def test_track_undo_false_still_clears_the_redo_stack(self):
        """Regression (PR #352 review): a flush-triggered commit (e.g. a
        note force-saved before a project-lifecycle transition) still
        genuinely changes project state even though it isn't itself pushed
        onto the undo stack -- a stale redo-stack entry recorded before that
        change must not survive it, or a later Redo could replay an
        unrelated future state on top of what was just committed."""
        executor = CommandExecutor()
        tracked = MockCommand("Tracked")
        executor.execute_command(tracked)
        executor.undo()
        assert len(executor.redo_stack) == 1

        flushed = MockCommand("Flushed")
        result = executor.execute_command(flushed, track_undo=False)

        assert result is True
        assert len(executor.redo_stack) == 0
        assert len(executor.undo_stack) == 0  # flushed itself still isn't pushed


class ResultCommand(MockCommand):
    """A MockCommand whose undo()/redo() return a caller-specified
    CommandResult, to test CommandExecutor's per-result stack handling
    (e.g. CommandResult.ABORTED)."""

    def __init__(self, name="ResultCommand", *, undo_result=None, redo_result=None):
        super().__init__(name)
        self._undo_result = undo_result
        self._redo_result = redo_result

    def undo(self):
        self.undo_count += 1
        return self._undo_result

    def redo(self):
        self.redo_count += 1
        return self._redo_result


class TestAbortedUndoRedo:
    """Test cases for CommandResult.ABORTED (PR #352 review): a precondition
    guard inside undo()/redo() (e.g. a failed flush) refused to make any
    change at all -- unlike FAILURE/NOOP, which still move the command to
    the opposite stack regardless (see CommandResult's docstring), ABORTED
    puts it back exactly where CommandExecutor found it, as if this call
    never happened."""

    def test_aborted_undo_puts_the_command_back_on_the_undo_stack(self):
        executor = CommandExecutor()
        command = ResultCommand("Aborted", undo_result=CommandResult.ABORTED)
        executor.execute_command(command)

        result = executor.undo()

        assert result is False
        assert len(executor.undo_stack) == 1
        assert executor.undo_stack[0] is command
        assert len(executor.redo_stack) == 0

    def test_aborted_undo_does_not_call_the_project_modified_hook(self):
        hook_calls = []
        executor = CommandExecutor(on_project_modified=lambda: hook_calls.append(1))
        command = ResultCommand("Aborted", undo_result=CommandResult.ABORTED)
        executor.execute_command(command)
        hook_calls.clear()

        executor.undo()

        assert hook_calls == []

    def test_aborted_undo_still_notifies_history_changed(self):
        """Even though nothing moved, can_undo()/can_redo() consumers (e.g.
        toolbar buttons) may care that an undo attempt just happened."""
        calls = []
        executor = CommandExecutor(on_history_changed=lambda: calls.append(1))
        command = ResultCommand("Aborted", undo_result=CommandResult.ABORTED)
        executor.execute_command(command)
        calls.clear()

        executor.undo()

        assert calls == [1]

    def test_aborted_redo_puts_the_command_back_on_the_redo_stack(self):
        executor = CommandExecutor()
        command = ResultCommand("Aborted", redo_result=CommandResult.ABORTED)
        executor.execute_command(command)
        executor.undo()

        result = executor.redo()

        assert result is False
        assert len(executor.redo_stack) == 1
        assert executor.redo_stack[0] is command
        assert len(executor.undo_stack) == 0

    def test_aborted_redo_does_not_call_the_project_modified_hook(self):
        hook_calls = []
        executor = CommandExecutor(on_project_modified=lambda: hook_calls.append(1))
        command = ResultCommand("Aborted", redo_result=CommandResult.ABORTED)
        executor.execute_command(command)
        executor.undo()
        hook_calls.clear()

        executor.redo()

        assert hook_calls == []


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
        # Dropped from both stacks entirely, so its held state (e.g. a large
        # DataFrame snapshot) must be released like any other stack eviction.
        assert command.cleanup_count == 1
    
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

    def test_undo_failure_invalidates_the_entire_history(self):
        """Commands here mutate shared live project/dataset objects rather
        than isolated snapshots, so once one command's undo() raises
        mid-operation the state it leaves behind is unknown -- any other
        stack entry may have been recorded against an assumption that no
        longer holds. The whole history must be dropped and cleaned up, not
        just the command that raised."""
        executor = CommandExecutor()
        older = MockCommand("Older")
        failing = MockCommand("Failing", should_fail=True, fail_on="undo")
        newer = MockCommand("Newer")
        executor.execute_command(older)
        executor.execute_command(failing)
        executor.execute_command(newer)
        executor.undo()  # newer -> redo_stack; undo_stack = [older, failing]

        result = executor.undo()  # pops `failing`; raises

        assert result is False
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
        assert older.cleanup_count == 1
        assert newer.cleanup_count == 1
        assert failing.cleanup_count == 1


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
        assert command.cleanup_count == 1
    
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

    def test_redo_failure_invalidates_the_entire_history(self):
        executor = CommandExecutor()
        already_undone = MockCommand("AlreadyUndone")
        failing = MockCommand("Failing", should_fail=True, fail_on="redo")
        executor.execute_command(already_undone)
        executor.execute_command(failing)
        newer = MockCommand("Newer")
        executor.execute_command(newer)
        executor.undo()  # newer -> redo_stack
        executor.undo()  # failing -> redo_stack
        executor.undo()  # already_undone -> redo_stack

        result = executor.redo()  # pops `already_undone`, redoes it fine
        assert result is True

        result = executor.redo()  # pops `failing`; raises

        assert result is False
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
        assert already_undone.cleanup_count == 1
        assert newer.cleanup_count == 1
        assert failing.cleanup_count == 1


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


class NonModifyingMockCommand(MockCommand):
    """A command that opts out of the dirty-tracking hook, mirroring the
    project-lifecycle commands (new/open/load/save/close), which manage
    AppState's modified flag themselves instead."""
    def marks_project_modified(self) -> bool:
        return False


class TestProjectModifiedHook:
    """Tests for CommandExecutor.on_project_modified, the hook AppState.
    mark_modified is wired to (see app.py's build_app_context)."""

    def test_successful_execute_calls_the_hook_by_default(self):
        executor = CommandExecutor()
        calls = []
        executor.on_project_modified = lambda: calls.append("modified")

        executor.execute_command(MockCommand())

        assert calls == ["modified"]

    def test_opted_out_command_does_not_call_the_hook(self):
        executor = CommandExecutor()
        calls = []
        executor.on_project_modified = lambda: calls.append("modified")

        executor.execute_command(NonModifyingMockCommand())

        assert calls == []

    def test_failed_execute_does_not_call_the_hook(self):
        executor = CommandExecutor()
        calls = []
        executor.on_project_modified = lambda: calls.append("modified")

        executor.execute_command(MockCommand(should_fail=True, fail_on="execute"))

        assert calls == []

    def test_undo_and_redo_call_the_hook_for_a_default_command(self):
        executor = CommandExecutor()
        calls = []
        executor.execute_command(MockCommand())
        executor.on_project_modified = lambda: calls.append("modified")

        executor.undo()
        executor.redo()

        assert calls == ["modified", "modified"]

    def test_no_hook_configured_is_a_no_op(self):
        """With on_project_modified left at its default None, execution must
        not raise (CommandExecutor is usable standalone, e.g. in tests that
        construct it without wiring AppState)."""
        executor = CommandExecutor()
        assert executor.execute_command(MockCommand()) is True

    def test_undo_that_raises_still_calls_the_hook(self):
        """A command's undo() can mutate the shared project/dataset state
        before raising, so the dirty flag must still be set even though the
        operation is reported as failed -- otherwise a save right after
        could mark that mutated state as clean."""
        executor = CommandExecutor()
        executor.execute_command(MockCommand("FailingCommand", should_fail=True, fail_on="undo"))
        calls = []
        executor.on_project_modified = lambda: calls.append("modified")

        executor.undo()

        assert calls == ["modified"]

    def test_redo_that_raises_still_calls_the_hook(self):
        executor = CommandExecutor()
        executor.execute_command(MockCommand("FailingCommand", should_fail=True, fail_on="redo"))
        executor.undo()
        calls = []
        executor.on_project_modified = lambda: calls.append("modified")

        executor.redo()

        assert calls == ["modified"]

    def test_a_raising_hook_does_not_prevent_recovery_from_a_failed_undo(self):
        """on_project_modified is an external callback (wired to
        AppState.mark_modified) invoked while undo() is already handling a
        command failure -- if it raises, recovery (history invalidation,
        the undo_redo_error hook, the history-changed notification) must
        still complete, same isolation as on_undo_redo_error and
        command.cleanup() already get."""
        executor = CommandExecutor()
        older = MockCommand("Older")
        failing = MockCommand("Failing", should_fail=True, fail_on="undo")
        executor.execute_command(older)
        executor.execute_command(failing)
        executor.on_project_modified = lambda: (_ for _ in ()).throw(RuntimeError("mark_modified failed"))
        history_calls = []
        executor.on_history_changed = lambda: history_calls.append(None)

        result = executor.undo()  # must not raise

        assert result is False
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
        assert older.cleanup_count == 1
        assert failing.cleanup_count == 1
        assert len(history_calls) == 1

    def test_a_raising_hook_does_not_prevent_recovery_from_a_failed_redo(self):
        executor = CommandExecutor()
        newer = MockCommand("Newer")
        failing = MockCommand("Failing", should_fail=True, fail_on="redo")
        executor.execute_command(failing)
        executor.execute_command(newer)
        executor.undo()
        executor.undo()
        executor.on_project_modified = lambda: (_ for _ in ()).throw(RuntimeError("mark_modified failed"))
        history_calls = []
        executor.on_history_changed = lambda: history_calls.append(None)

        result = executor.redo()  # must not raise

        assert result is False
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
        assert newer.cleanup_count == 1
        assert failing.cleanup_count == 1
        assert len(history_calls) == 1

    def test_a_raising_marks_project_modified_does_not_prevent_recovery_from_a_failed_undo(self):
        """marks_project_modified() is itself overridable, so it can raise
        just like on_project_modified can -- it must get the same isolation,
        since it now runs inside the same try as the hook it gates."""

        class RaisingMarksProjectModifiedCommand(MockCommand):
            def marks_project_modified(self) -> bool:
                raise RuntimeError("marks_project_modified failed")

        executor = CommandExecutor()
        older = MockCommand("Older")
        failing = RaisingMarksProjectModifiedCommand("Failing", should_fail=True, fail_on="undo")
        executor.execute_command(older)
        executor.execute_command(failing)
        calls = []
        executor.on_project_modified = lambda: calls.append("modified")
        history_calls = []
        executor.on_history_changed = lambda: history_calls.append(None)

        result = executor.undo()  # must not raise

        assert result is False
        assert calls == []
        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
        assert older.cleanup_count == 1
        assert failing.cleanup_count == 1
        assert len(history_calls) == 1

    def test_marks_project_modified_is_evaluated_before_cleanup_runs(self):
        """marks_project_modified() may derive its answer from state
        cleanup() releases (e.g. whether an undo snapshot was captured), so
        on undo/redo failure it must be evaluated before
        _invalidate_history_after_failure() calls cleanup() on the command
        -- the same ordering hazard already fixed for display_name()."""

        class ModifiedFlagFromStateCommand(MockCommand):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.snapshot = "captured"

            def marks_project_modified(self) -> bool:
                return self.snapshot is not None

            def cleanup(self):
                super().cleanup()
                self.snapshot = None

        executor = CommandExecutor()
        command = ModifiedFlagFromStateCommand("Failing", should_fail=True, fail_on="undo")
        executor.execute_command(command)
        calls = []
        executor.on_project_modified = lambda: calls.append("modified")

        executor.undo()

        assert calls == ["modified"]


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


class TestHistoryChangedHook:
    """Regression (#206): the Edit menu's Undo/Redo actions need to know
    whenever can_undo()/can_redo() may have changed, so they can stay
    correctly enabled/disabled instead of always being enabled regardless
    of stack state. on_history_changed is the hook main_menu.py wires up
    for that (via AppEvents.HISTORY_CHANGED -- see test_main_menu.py)."""

    def test_execute_command_notifies(self):
        executor = CommandExecutor()
        calls = []
        executor.on_history_changed = lambda: calls.append(None)

        executor.execute_command(MockCommand())

        assert len(calls) == 1

    def test_failed_execute_command_does_not_notify(self):
        executor = CommandExecutor()
        calls = []
        executor.on_history_changed = lambda: calls.append(None)

        executor.execute_command(MockCommand(should_fail=True, fail_on="execute"))

        assert calls == []

    def test_undo_notifies(self):
        executor = CommandExecutor()
        executor.execute_command(MockCommand())
        calls = []
        executor.on_history_changed = lambda: calls.append(None)

        executor.undo()

        assert len(calls) == 1

    def test_undo_on_empty_stack_does_not_notify(self):
        executor = CommandExecutor()
        calls = []
        executor.on_history_changed = lambda: calls.append(None)

        executor.undo()

        assert calls == []

    def test_redo_notifies(self):
        executor = CommandExecutor()
        executor.execute_command(MockCommand())
        executor.undo()
        calls = []
        executor.on_history_changed = lambda: calls.append(None)

        executor.redo()

        assert len(calls) == 1

    def test_clear_history_notifies(self):
        executor = CommandExecutor()
        executor.execute_command(MockCommand())
        calls = []
        executor.on_history_changed = lambda: calls.append(None)

        executor.clear_history()

        assert len(calls) == 1

    def test_no_hook_set_does_not_raise(self):
        """The hook is optional (None by default) -- every call site must
        tolerate that, not just the ones under test above."""
        executor = CommandExecutor()
        executor.execute_command(MockCommand())
        executor.undo()
        executor.redo()
        executor.clear_history()  # must not raise

    def test_a_raising_hook_does_not_break_execute_commands_return_value(self):
        """on_history_changed is called right before undo()/redo()/
        execute_command() return -- a raising hook must not escape and take
        the True/False return with it, same isolation as
        on_project_modified/on_undo_redo_error already get."""
        executor = CommandExecutor()
        executor.on_history_changed = lambda: (_ for _ in ()).throw(RuntimeError("listener failed"))

        result = executor.execute_command(MockCommand())  # must not raise

        assert result is True

    def test_a_raising_hook_does_not_break_a_successful_undo_or_redo(self):
        executor = CommandExecutor()
        command = MockCommand()
        executor.execute_command(command)
        executor.on_history_changed = lambda: (_ for _ in ()).throw(RuntimeError("listener failed"))

        undo_result = executor.undo()  # must not raise
        redo_result = executor.redo()  # must not raise

        assert undo_result is True
        assert redo_result is True

    def test_a_raising_hook_does_not_break_undo_or_redo_failure_reporting(self):
        executor = CommandExecutor()
        executor.execute_command(MockCommand("FailingCommand", should_fail=True, fail_on="undo"))
        executor.on_history_changed = lambda: (_ for _ in ()).throw(RuntimeError("listener failed"))

        result = executor.undo()  # must not raise

        assert result is False

    def test_a_raising_hook_does_not_break_clear_history(self):
        executor = CommandExecutor()
        executor.execute_command(MockCommand())
        executor.on_history_changed = lambda: (_ for _ in ()).throw(RuntimeError("listener failed"))

        executor.clear_history()  # must not raise

        assert len(executor.undo_stack) == 0

    def test_undo_failure_still_notifies(self):
        """The stacks changed (the command was dropped) even though undo()
        raised, so the Edit menu still needs to refresh its enabled state."""
        executor = CommandExecutor()
        executor.execute_command(MockCommand("FailingCommand", should_fail=True, fail_on="undo"))
        calls = []
        executor.on_history_changed = lambda: calls.append(None)

        executor.undo()

        assert len(calls) == 1

    def test_redo_failure_still_notifies(self):
        executor = CommandExecutor()
        executor.execute_command(MockCommand("FailingCommand", should_fail=True, fail_on="redo"))
        executor.undo()
        calls = []
        executor.on_history_changed = lambda: calls.append(None)

        executor.redo()

        assert len(calls) == 1


class TestUndoRedoErrorHook:
    """Tests for CommandExecutor.on_undo_redo_error, the hook that lets the
    UI tell the user their undo/redo history was reset because a command's
    undo()/redo() raised mid-operation (issue #285): since commands mutate
    shared live project state rather than isolated snapshots, a partial
    failure makes every remaining stack entry's assumed state suspect, so
    the whole history is invalidated rather than just the failed command --
    see TestUndoFunctionality.test_undo_failure_invalidates_the_entire_history."""

    def test_undo_failure_calls_the_hook_with_command_display_name_and_operation(self):
        executor = CommandExecutor()
        executor.execute_command(MockCommand("FailingCommand", should_fail=True, fail_on="undo"))
        calls = []
        executor.on_undo_redo_error = lambda command_description, operation: calls.append((command_description, operation))

        executor.undo()

        assert calls == [("Mock", "undo")]

    def test_redo_failure_calls_the_hook_with_command_display_name_and_operation(self):
        executor = CommandExecutor()
        executor.execute_command(MockCommand("FailingCommand", should_fail=True, fail_on="redo"))
        executor.undo()
        calls = []
        executor.on_undo_redo_error = lambda command_description, operation: calls.append((command_description, operation))

        executor.redo()

        assert calls == [("Mock", "redo")]

    def test_successful_undo_does_not_call_the_hook(self):
        executor = CommandExecutor()
        executor.execute_command(MockCommand())
        calls = []
        executor.on_undo_redo_error = lambda command_description, operation: calls.append((command_description, operation))

        executor.undo()

        assert calls == []

    def test_successful_redo_does_not_call_the_hook(self):
        executor = CommandExecutor()
        executor.execute_command(MockCommand())
        executor.undo()
        calls = []
        executor.on_undo_redo_error = lambda command_description, operation: calls.append((command_description, operation))

        executor.redo()

        assert calls == []

    def test_no_hook_configured_is_a_no_op(self):
        """The hook is optional (None by default) -- a raising undo()/redo()
        must not itself raise just because nothing is listening."""
        executor = CommandExecutor()
        executor.execute_command(MockCommand("FailingCommand", should_fail=True, fail_on="undo"))

        result = executor.undo()

        assert result is False

    def test_a_raising_hook_does_not_prevent_recovery(self):
        """The hook itself (e.g. a Qt dialog) could raise. It runs while
        undo()/redo() is already handling a command failure, so a hook
        exception must not escape and skip the history-changed notification
        that follows it -- same isolation as _safe_cleanup gives
        command.cleanup()."""
        executor = CommandExecutor()
        executor.execute_command(MockCommand("FailingCommand", should_fail=True, fail_on="undo"))
        executor.on_undo_redo_error = lambda command_description, operation: (_ for _ in ()).throw(RuntimeError("dialog failed"))
        history_calls = []
        executor.on_history_changed = lambda: history_calls.append(None)

        result = executor.undo()  # must not raise

        assert result is False
        assert len(history_calls) == 1

    def test_a_raising_display_name_falls_back_to_the_class_name(self):
        """display_name() is itself overridable and could raise -- it must
        not prevent failure recovery, and the hook should still get a usable
        label (the class name) instead of nothing."""

        class RaisingDisplayNameCommand(MockCommand):
            def display_name(self) -> str:
                raise RuntimeError("display_name failed")

        executor = CommandExecutor()
        executor.execute_command(RaisingDisplayNameCommand("Failing", should_fail=True, fail_on="undo"))
        calls = []
        executor.on_undo_redo_error = lambda command_description, operation: calls.append((command_description, operation))

        result = executor.undo()  # must not raise

        assert result is False
        assert calls == [("RaisingDisplayNameCommand", "undo")]

    def test_display_name_is_resolved_before_cleanup_runs(self):
        """display_name() may derive its label from state cleanup() releases
        (e.g. a snapshot's identifying name), so it must be resolved before
        _invalidate_history_after_failure() calls cleanup() on the command."""

        class NameFromStateCommand(MockCommand):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.state = "still here"

            def display_name(self) -> str:
                return self.state

            def cleanup(self):
                super().cleanup()
                self.state = None

        executor = CommandExecutor()
        executor.execute_command(NameFromStateCommand("Failing", should_fail=True, fail_on="undo"))
        calls = []
        executor.on_undo_redo_error = lambda command_description, operation: calls.append((command_description, operation))

        executor.undo()

        assert calls == [("still here", "undo")]


class TestCleanupOnEviction:
    """Test cases for Command.cleanup() being called when a command is
    dropped from a stack outside the normal undo/redo lifecycle."""

    def test_cleanup_called_on_eviction_past_max_undo_levels(self):
        executor = CommandExecutor()
        executor.max_undo_levels = 2
        cmd1 = MockCommand("Command1")
        cmd2 = MockCommand("Command2")
        cmd3 = MockCommand("Command3")

        executor.execute_command(cmd1)
        executor.execute_command(cmd2)
        assert cmd1.cleanup_count == 0

        executor.execute_command(cmd3)  # evicts cmd1

        assert cmd1.cleanup_count == 1
        assert cmd2.cleanup_count == 0
        assert cmd3.cleanup_count == 0

    def test_cleanup_called_on_redo_stack_clear(self):
        executor = CommandExecutor()
        cmd1 = MockCommand("Command1")
        cmd2 = MockCommand("Command2")

        executor.execute_command(cmd1)
        executor.undo()
        assert len(executor.redo_stack) == 1

        executor.execute_command(cmd2)  # clears redo_stack, dropping cmd1's redo entry

        assert cmd1.cleanup_count == 1

    def test_cleanup_called_on_clear_history(self):
        executor = CommandExecutor()
        cmd1 = MockCommand("Command1")
        cmd2 = MockCommand("Command2")

        executor.execute_command(cmd1)
        executor.execute_command(cmd2)
        executor.undo()  # cmd2 -> redo_stack, cmd1 stays on undo_stack

        executor.clear_history()

        assert cmd1.cleanup_count == 1
        assert cmd2.cleanup_count == 1

    def test_cleanup_not_called_on_ordinary_undo_redo(self):
        """Moving a command between undo_stack and redo_stack via undo()/redo()
        must not release its state -- it may still be needed."""
        executor = CommandExecutor()
        command = MockCommand("TestCommand")

        executor.execute_command(command)
        executor.undo()
        executor.redo()
        executor.undo()

        assert command.cleanup_count == 0


class TestCleanupExceptionIsolation:
    """A raising cleanup() must never corrupt CommandExecutor's own control
    flow: it can't turn a successful execute_command() into a reported
    failure, and it can't prevent the redo/undo stacks from being cleared or
    prevent cleanup from being attempted on the remaining stack entries."""

    def test_execute_command_still_succeeds_when_evicted_commands_cleanup_raises(self):
        executor = CommandExecutor()
        executor.max_undo_levels = 1
        cmd1 = RaisingCleanupCommand("Command1")
        cmd2 = MockCommand("Command2")

        executor.execute_command(cmd1)

        result = executor.execute_command(cmd2)  # evicts cmd1; cmd1.cleanup() raises

        assert result is True
        assert cmd1.cleanup_count == 1
        assert len(executor.undo_stack) == 1
        assert executor.undo_stack[0] is cmd2

    def test_redo_stack_fully_cleared_when_a_stale_commands_cleanup_raises(self):
        executor = CommandExecutor()
        cmd1 = RaisingCleanupCommand("Command1")
        cmd2 = MockCommand("Command2")
        cmd3 = MockCommand("Command3")

        executor.execute_command(cmd1)
        executor.execute_command(cmd2)
        executor.undo()
        executor.undo()
        assert len(executor.redo_stack) == 2

        result = executor.execute_command(cmd3)  # clears redo_stack; cmd1.cleanup() raises

        assert result is True
        assert len(executor.redo_stack) == 0
        assert cmd1.cleanup_count == 1

    def test_clear_history_clears_both_stacks_and_cleans_up_remaining_commands_when_one_raises(self):
        executor = CommandExecutor()
        cmd1 = RaisingCleanupCommand("Command1")
        cmd2 = MockCommand("Command2")
        cmd3 = MockCommand("Command3")

        executor.execute_command(cmd1)
        executor.execute_command(cmd2)
        executor.execute_command(cmd3)
        executor.undo()  # cmd3 -> redo_stack

        executor.clear_history()

        assert len(executor.undo_stack) == 0
        assert len(executor.redo_stack) == 0
        assert cmd1.cleanup_count == 1
        assert cmd2.cleanup_count == 1
        assert cmd3.cleanup_count == 1


class TestEdgeCases:
    """Test edge cases and complex scenarios."""
    
    def test_command_state_after_execution_failure(self):
        """Test command state when execution fails."""
        executor = CommandExecutor()
        command = MockCommand("FailingCommand", should_fail=True, fail_on="execute")
        
        with patch("builtins.print"):
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
        
        with patch("builtins.print"):
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
