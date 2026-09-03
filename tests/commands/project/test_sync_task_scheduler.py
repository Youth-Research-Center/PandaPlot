"""Tests for SyncTaskScheduler test double."""

from tests.commands.project.conftest import SyncTaskScheduler


def test_sync_task_scheduler_calls_result_then_finished_on_success():
    calls = []
    scheduler = SyncTaskScheduler()

    def task(progress_callback, value):
        return value * 2

    scheduler.run_task(
        task,
        task_arguments={"value": 21},
        on_result=lambda r: calls.append(("result", r)),
        on_finished=lambda: calls.append(("finished", None)),
    )

    assert calls == [("result", 42), ("finished", None)]


def test_sync_task_scheduler_calls_error_then_finished_on_exception():
    calls = []
    scheduler = SyncTaskScheduler()

    def task(progress_callback):
        raise ValueError("boom")

    scheduler.run_task(
        task,
        on_error=lambda err: calls.append(("error", err[1])),
        on_finished=lambda: calls.append(("finished", None)),
    )

    assert len(calls) == 2
    assert calls[0][0] == "error"
    assert isinstance(calls[0][1], ValueError)
    assert calls[1] == ("finished", None)
