"""Shared fixtures for command tests that dispatch work via TaskScheduler."""

import traceback
from typing import Any, Callable, Optional

import pytest


class SyncTaskScheduler:
    """Drop-in TaskScheduler replacement that runs the task synchronously,
    inline, instead of on a QThreadPool thread. Mirrors Worker.run()'s
    try/except/else/finally shape exactly so command code under test behaves
    identically to production, just without real threading."""

    def run_task(
        self,
        task: Callable[..., Any],
        task_arguments: Optional[dict] = None,
        on_result: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[tuple], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> None:
        task_arguments = task_arguments if task_arguments is not None else {}
        progress_callback = on_progress if on_progress is not None else (lambda _p: None)
        try:
            result = task(progress_callback=progress_callback, **task_arguments)
        except Exception as e:
            if on_error:
                on_error((type(e), e, traceback.format_exc()))
        else:
            if on_result:
                on_result(result)
        finally:
            if on_finished:
                on_finished()


@pytest.fixture
def sync_task_scheduler():
    return SyncTaskScheduler()
