"""pytest-xdist scheduler that survives a crashed worker.

Registered from ``tests/conftest.py`` so it is active on the xdist controller.
"""

from __future__ import annotations

import pytest
from xdist.remote import Producer
from xdist.scheduler import LoadFileScheduling
from xdist.workermanage import WorkerController


class CrashSafeLoadFileScheduling(LoadFileScheduling):
    """``loadfile`` scheduling that neither deadlocks nor re-runs the crashed test.

    xdist's ``LoadScopeScheduling.remove_node`` puts the crashed worker's whole
    workload back on the queue, including files whose tests had all completed.
    Handing such a file out sends an empty batch; a worker holds its last test
    until it receives another test or a shutdown, so that worker never finishes
    and the session hangs. xdist also leaves the crashed test marked as not
    completed, so it runs again on another worker, and a test that crashes every
    time exhausts ``--max-worker-restart``.

    This scheduler marks the crashed test completed (xdist still reports it as a
    failure) and re-queues only the files that still have pending tests.
    """

    def remove_node(self, node: WorkerController) -> str | None:
        """Remove a node and re-schedule only its unfinished work.

        Args:
            node: The worker that finished or crashed.

        Returns:
            The nodeid of the test that was running when the worker crashed, or
            None if the worker had no pending tests.

        Raises:
            RuntimeError: If the workload has pending tests but none can be found.
        """
        workload = self.assigned_work.pop(node)
        if not self._pending_of(workload):
            return None

        crashitem: str | None = None
        for work_unit in workload.values():
            for nodeid, completed in work_unit.items():
                if not completed:
                    crashitem = nodeid
                    break
            if crashitem is not None:
                break
        if crashitem is None:
            raise RuntimeError("Unable to identify crashitem on a workload with pending items")

        for work_unit in workload.values():
            if crashitem in work_unit:
                work_unit[crashitem] = True

        self.workqueue.update({scope: unit for scope, unit in workload.items() if not all(unit.values())})

        for remaining in self.assigned_work:
            self._reschedule(remaining)

        return crashitem


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_make_scheduler(config: pytest.Config, log: Producer) -> CrashSafeLoadFileScheduling | None:
    """Use the crash-safe scheduler for ``--dist=loadfile`` and defer to xdist otherwise.

    Args:
        config: The pytest config of the controller.
        log: The xdist logging producer.

    Returns:
        The scheduler for ``loadfile``, otherwise None.
    """
    if config.getoption("dist") == "loadfile":
        return CrashSafeLoadFileScheduling(config, log)
    return None
