import time

import pytest
from PySide6.QtCore import QCoreApplication

from pandaplot.services.qtasks import CancellationToken, TaskCancelledError, TaskScheduler
from pandaplot.services.qtasks.cancellation import build_cancellation_kwargs

# Bound on how long a test worker loop may run for. If a cancellation
# regression stops the token from ever being marked cancelled, the worker
# loop breaks on this deadline and waitForDone() times out on WAIT_MSECS,
# so the test fails with an assertion instead of hanging the whole run.
LOOP_DEADLINE_SECONDS = 2.0
WAIT_MSECS = int((LOOP_DEADLINE_SECONDS + 3.0) * 1000)


def test_cancellation_token_basic():
    token = CancellationToken()
    assert not token.is_cancelled()
    assert not token()

    token.cancel()
    assert token.is_cancelled()
    assert token()


def test_cancellation_token_raise():
    token = CancellationToken()
    token.raise_if_cancelled()  # should not raise

    token.cancel()
    with pytest.raises(TaskCancelledError):
        token.raise_if_cancelled()


def test_build_cancellation_kwargs_skips_positional_only_params():
    def task(is_cancelled, /, progress_callback):
        pass

    # is_cancelled is positional-only, so it must not be injected as a
    # keyword - doing so would raise a TypeError when the task is called.
    assert build_cancellation_kwargs(task, CancellationToken()) == {}


def test_build_cancellation_kwargs_injects_regular_params():
    def task(progress_callback, is_cancelled, cancellation_token):
        pass

    token = CancellationToken()
    kwargs = build_cancellation_kwargs(task, token)
    assert kwargs == {"is_cancelled": token.is_cancelled, "cancellation_token": token}


def test_build_cancellation_kwargs_injects_via_var_keyword():
    def task(progress_callback, **kwargs):
        pass

    token = CancellationToken()
    kwargs = build_cancellation_kwargs(task, token)
    assert kwargs == {"is_cancelled": token.is_cancelled, "cancellation_token": token}


def test_task_scheduler_cancellation_polled(qapp):
    scheduler = TaskScheduler()
    events = []

    def task(progress_callback, is_cancelled):
        for _ in range(10):
            if is_cancelled():
                raise TaskCancelledError()
            time.sleep(0.01)
        return "completed"

    token = scheduler.run_task(
        task,
        on_result=lambda r: events.append(("result", r)),
        on_cancelled=lambda: events.append(("cancelled", None)),
        on_finished=lambda: events.append(("finished", None)),
    )

    token.cancel()
    scheduler.threadpool.waitForDone()
    QCoreApplication.processEvents()

    assert ("cancelled", None) in events
    assert ("finished", None) in events
    assert ("result", "completed") not in events


def test_task_scheduler_cancel_task_by_token(qapp):
    scheduler = TaskScheduler()
    events = []

    def task(progress_callback, cancellation_token):
        deadline = time.monotonic() + LOOP_DEADLINE_SECONDS
        while not cancellation_token.is_cancelled() and time.monotonic() < deadline:
            time.sleep(0.01)

    token = scheduler.run_task(
        task,
        on_cancelled=lambda: events.append("cancelled"),
        on_finished=lambda: events.append("finished"),
    )

    cancelled = scheduler.cancel_task(token)
    assert scheduler.threadpool.waitForDone(WAIT_MSECS)
    QCoreApplication.processEvents()

    assert cancelled is True
    assert "cancelled" in events
    assert "finished" in events


def test_task_scheduler_cancel_all(qapp):
    scheduler = TaskScheduler()
    events = []

    def task1(progress_callback, is_cancelled):
        deadline = time.monotonic() + LOOP_DEADLINE_SECONDS
        while not is_cancelled() and time.monotonic() < deadline:
            time.sleep(0.01)

    def task2(progress_callback, is_cancelled):
        deadline = time.monotonic() + LOOP_DEADLINE_SECONDS
        while not is_cancelled() and time.monotonic() < deadline:
            time.sleep(0.01)

    scheduler.run_task(task1, on_cancelled=lambda: events.append("t1_cancelled"))
    scheduler.run_task(task2, on_cancelled=lambda: events.append("t2_cancelled"))

    scheduler.cancel_all()
    assert scheduler.threadpool.waitForDone(WAIT_MSECS)
    QCoreApplication.processEvents()

    assert "t1_cancelled" in events
    assert "t2_cancelled" in events
