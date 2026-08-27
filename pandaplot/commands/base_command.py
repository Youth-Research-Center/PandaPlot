import logging
from abc import ABC, abstractmethod


class Command(ABC):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def execute(self) -> bool:
        pass

    @abstractmethod
    def undo(self):
        pass

    @abstractmethod
    def redo(self):
        pass

    def occupies_undo_slot(self) -> bool:
        """Whether this command should be pushed onto/moved between the
        undo/redo stacks. Default True; override to False for a command
        whose real effect doesn't happen synchronously inside execute() --
        e.g. one that opens a dialog and does its actual work later, in a
        callback, via its own execute_command() call (see
        CreateChartFromWizardCommand)."""
        return True

    def cleanup(self) -> None:
        """Called by CommandExecutor when this command is dropped from a
        stack outside the normal undo/redo lifecycle: eviction past
        max_undo_levels, a redo-stack clear, or clear_history(). Not called
        when the command is merely moved between undo_stack and redo_stack
        by undo()/redo(), since it may still need its state then. Default
        no-op; override to release resources held for undo (e.g. a large
        DataFrame snapshot). (Note: a command whose own `undo()`/`redo()`
        raises is also dropped without a `cleanup()` call -- a pre-existing
        gap in the executor's exception handling, not addressed here.)"""
        return

    def __repr__(self):
        return f"{self.__class__.__name__}()"
