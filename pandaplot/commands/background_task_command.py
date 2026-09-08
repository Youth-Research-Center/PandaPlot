import logging
from typing import Any, Callable, Optional, override

from pandaplot.commands.base_command import Command, CommandResult


class BackgroundTaskCommand(Command):
    """Base class for commands that dispatch asynchronous computations to a
    background thread via TaskScheduler.

    Provides a shared scaffold for:
    - _is_running re-entrancy protection.
    - Default non-undoable command behaviors (occupies_undo_slot=False,
      marks_project_modified=False, default undo/redo no-ops).
    - Standard outcome dictionary wrapping for thread signal safety
      ({"success": bool, "result": Any, "error": str | None}).
    - Dispatch project capturing and staleness checking.
    - Uniform completion callback notification (_notify_complete).
    """

    def __init__(self, on_complete: Optional[Callable[[CommandResult], None]] = None):
        super().__init__()
        self.on_complete = on_complete
        self._is_running = False
        self._dispatch_project = None

    @override
    def occupies_undo_slot(self) -> bool:
        """Background dispatch commands do not occupy undo slots by default;
        the real undoable effect (if any) is applied via a separate command when
        the background computation finishes."""
        return False

    @override
    def marks_project_modified(self) -> bool:
        """Background dispatch commands do not mark project modified by default."""
        return False

    @override
    def undo(self) -> CommandResult:
        """Default no-op for non-undoable background dispatch commands."""
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        """Default no-op for non-undoable background dispatch commands."""
        return CommandResult.SUCCESS

    def _notify_complete(self, result: CommandResult) -> None:
        """Invoke on_complete callback if set."""
        if self.on_complete:
            self.on_complete(result)

    def _capture_dispatch_project(self, app_context) -> None:
        """Capture the active project at dispatch time to detect mid-computation project switches."""
        self._dispatch_project = app_context.get_app_state().current_project

    def _is_project_stale(self, app_context) -> bool:
        """Check if the current project differs from the project active at dispatch time."""
        return app_context.get_app_state().current_project is not self._dispatch_project

    @staticmethod
    def _run_task_safely(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Helper to run a function safely in a background thread task, catching
        exceptions and returning a standard signal-friendly outcome dictionary."""
        try:
            res = fn(*args, **kwargs)
            if res is None:
                return {"success": False, "result": None, "error": "Computation returned no result"}
            return {"success": True, "result": res, "error": None}
        except Exception as e:
            logging.getLogger("BackgroundTaskCommand").error("Background computation failed: %s", e, exc_info=True)
            return {"success": False, "result": None, "error": str(e)}

    def _dispatch_task(
        self,
        task_scheduler,
        task: Callable[..., Any],
        task_arguments: Optional[dict[str, Any]] = None,
        on_result: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Any], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        """Dispatch a background task via task_scheduler with _is_running lifecycle tracking."""
        self._is_running = True

        def _finished_wrapper():
            try:
                if on_finished:
                    on_finished()
            finally:
                self._is_running = False

        task_scheduler.run_task(
            task=task,
            task_arguments=task_arguments,
            on_result=on_result,
            on_error=on_error,
            on_finished=_finished_wrapper,
        )
