"""Tests for Worker error reporting."""

import logging

from pandaplot.services.qtasks.worker import Worker


def test_failing_task_is_logged_with_traceback_and_reported(caplog):
    def failing_task(progress_callback):
        raise RuntimeError("boom")

    worker = Worker(failing_task)
    errors = []
    worker.signals.error.connect(errors.append)

    with caplog.at_level(logging.ERROR):
        worker.run()

    records = [r for r in caplog.records if r.levelno == logging.ERROR and r.exc_info is not None]
    assert len(records) == 1
    assert records[0].exc_info[0] is RuntimeError
    assert len(errors) == 1
    assert errors[0][0] is RuntimeError
    assert "boom" in errors[0][2]
