import logging
import re
from abc import ABC, abstractmethod
from enum import StrEnum


class CommandResult(StrEnum):
    """Outcome of `Command.execute()`/`undo()`/`redo()`.

    SUCCESS/FAILURE/NOOP determine `CommandExecutor`'s log level (info,
    warning, debug respectively) and, for `execute()`, whether the command is
    pushed onto the undo stack (SUCCESS only; FAILURE and NOOP are not).
    `undo()`/`redo()` always move the command between stacks regardless of
    result -- EXCEPT for ABORTED (see below).

    Always compare explicitly (`if command.execute() is
    CommandResult.SUCCESS:`) -- every member is truthy, so `if
    command.execute():` would silently pass regardless of outcome.
    """
    SUCCESS = "success"
    FAILURE = "failure"
    NOOP = "noop"
    # undo()/redo() only: a precondition guard refused to make any change at
    # all (e.g. a note edit couldn't be flushed first) -- unlike
    # FAILURE/NOOP, which still move the command to the opposite stack,
    # ABORTED puts it back exactly where CommandExecutor found it (undo_stack
    # for undo(), redo_stack for redo()), as if this call never happened.
    # Must not be returned from execute().
    ABORTED = "aborted"


class Command(ABC):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def execute(self) -> CommandResult:
        pass

    @abstractmethod
    def undo(self) -> CommandResult:
        pass

    @abstractmethod
    def redo(self) -> CommandResult:
        pass

    def occupies_undo_slot(self) -> bool:
        """Whether this command should be pushed onto/moved between the
        undo/redo stacks. Default True; override to False for a command
        whose real effect doesn't happen synchronously inside execute() --
        e.g. one that opens a dialog and does its actual work later, in a
        callback, via its own execute_command() call (see
        CreateChartFromWizardCommand)."""
        return True

    def marks_project_modified(self) -> bool:
        """Whether a successful execute()/undo()/redo() of this command
        should flag the project as having unsaved changes (see
        CommandExecutor.on_project_modified). Default True; override to
        False for project-lifecycle commands (new/open/load/save/close),
        which manage AppState's modified flag explicitly instead."""
        return True

    def display_name(self) -> str:
        """Human-readable name for this command, shown to the user (e.g. in
        an undo/redo error dialog) -- unlike `__class__.__name__`, which is
        an implementation identifier not meant for user-facing text. Default
        derives one from the class name (e.g. CreateNoteCommand -> "Create
        note"); override for a custom label."""
        name = self.__class__.__name__
        if name.endswith("Command"):
            name = name[: -len("Command")]
        words = re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", name)
        if not words:
            return self.__class__.__name__
        return " ".join([words[0]] + [w.lower() for w in words[1:]])

    def cleanup(self) -> None:
        """Called by CommandExecutor when this command is dropped from a
        stack outside the normal undo/redo lifecycle: eviction past
        max_undo_levels, a redo-stack clear, or clear_history(). Not called
        when the command is merely moved between undo_stack and redo_stack
        by undo()/redo(), since it may still need its state then. Default
        no-op; override to release resources held for undo (e.g. a large
        DataFrame snapshot). Also called when *any* command on either stack
        raises out of its own `undo()`/`redo()` -- the whole history is
        invalidated and cleaned up in that case (see
        CommandExecutor._invalidate_history_after_failure), not just the
        command that raised, so overrides can't assume this only fires for
        their own failed undo()/redo()."""
        return

    def __repr__(self):
        return f"{self.__class__.__name__}()"
