"""Shared fixtures for command tests that dispatch work via TaskScheduler."""

import traceback
from typing import Any, Callable, Optional, Union

import pytest

from pandaplot.services.qtasks.cancellation import (
    CancellationToken,
    TaskCancelledError,
    build_cancellation_kwargs,
)

_RESERVED_TASK_ARGUMENT_KEYS = {"cancellation_token", "is_cancelled", "progress_callback"}


class SyncTaskScheduler:
    """Drop-in TaskScheduler replacement that runs the task synchronously,
    inline, instead of on a QThreadPool thread. Mirrors Worker.run()'s
    try/except/else/finally shape exactly so command code under test behaves
    identically to production, just without real threading."""

    def __init__(self) -> None:
        self._active_tokens: list[tuple[Callable[..., Any], CancellationToken]] = []

    def run_task(
        self,
        task: Callable[..., Any],
        task_arguments: Optional[dict] = None,
        on_result: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[tuple], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
        on_progress: Optional[Callable[[float], None]] = None,
        on_cancelled: Optional[Callable[[], None]] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> CancellationToken:
        task_arguments = task_arguments if task_arguments is not None else {}
        conflicting_keys = _RESERVED_TASK_ARGUMENT_KEYS & task_arguments.keys()
        if conflicting_keys:
            raise ValueError(
                f"task_arguments must not include reserved keys: {sorted(conflicting_keys)}"
            )
        token = cancellation_token or CancellationToken()
        entry = (task, token)
        self._active_tokens.append(entry)

        def _discard_entry():
            try:
                self._active_tokens.remove(entry)
            except ValueError:
                pass

        progress_callback = on_progress if on_progress is not None else (lambda _p: None)
        extra_kwargs = build_cancellation_kwargs(task, token)

        all_kwargs = {**task_arguments, "progress_callback": progress_callback, **extra_kwargs}

        if token.is_cancelled():
            try:
                try:
                    if on_cancelled:
                        on_cancelled()
                finally:
                    if on_finished:
                        on_finished()
            finally:
                _discard_entry()
            return token

        try:
            result = task(**all_kwargs)
            if token.is_cancelled():
                raise TaskCancelledError("Task was cancelled.")
        except TaskCancelledError:
            if on_cancelled:
                on_cancelled()
        except Exception as e:
            # Any exception other than TaskCancelledError is a genuine task
            # failure, even if cancellation happens to have been requested
            # around the same time - do not misreport it as a cancellation.
            if on_error:
                on_error((type(e), e, traceback.format_exc()))
        else:
            if on_result:
                on_result(result)
        finally:
            try:
                if on_finished:
                    on_finished()
            finally:
                _discard_entry()

        return token

    def cancel_task(self, task_or_token: Union[Callable[..., Any], CancellationToken]) -> bool:
        cancelled_any = False
        for fn, token in list(self._active_tokens):
            if token == task_or_token or fn == task_or_token:
                token.cancel()
                cancelled_any = True
        return cancelled_any

    def cancel_all(self) -> None:
        for _fn, token in list(self._active_tokens):
            token.cancel()


@pytest.fixture
def sync_task_scheduler():
    return SyncTaskScheduler()
