"""pytest-xdist scheduler that survives a crashed worker.

Registered from ``tests/conftest.py`` so it is active on the xdist controller.
"""

from __future__ import annotations

import warnings
from importlib.metadata import version

import pytest
from xdist.remote import Producer
from xdist.scheduler import LoadFileScheduling
from xdist.workermanage import WorkerController

SUPPORTED_XDIST_SERIES = (3, 8)
"""The pytest-xdist ``major.minor`` whose private scheduler internals this module was checked against.

``remove_node`` relies on ``assigned_work``, ``workqueue``, ``_pending_of`` and ``_reschedule``. On any
other series the controller falls back to xdist's own scheduler instead of risking an internal error in
exactly the crash case this module guards; re-check those internals before raising this.
"""


def is_supported_xdist(xdist_version: str) -> bool:
    """Return whether ``xdist_version`` is in the series this scheduler was checked against.

    Args:
        xdist_version: The installed pytest-xdist version, e.g. ``"3.8.0"``.

    Returns:
        True if its ``major.minor`` equals ``SUPPORTED_XDIST_SERIES``.
    """
    parts = xdist_version.split(".")[:2]
    try:
        return tuple(int(part) for part in parts) == SUPPORTED_XDIST_SERIES
    except ValueError:
        return False


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
        The scheduler for ``loadfile`` on a supported pytest-xdist series, otherwise None.
    """
    if config.getoption("dist") != "loadfile":
        return None
    xdist_version = version("pytest-xdist")
    if not is_supported_xdist(xdist_version):
        supported = ".".join(str(part) for part in SUPPORTED_XDIST_SERIES)
        warnings.warn(
            f"tests/xdist_crash_safe.py was checked against pytest-xdist {supported}.x, not {xdist_version}; "
            "using xdist's default loadfile scheduler (a crashed worker may hang the run).",
            pytest.PytestWarning,
            stacklevel=1,
        )
        return None
    return CrashSafeLoadFileScheduling(config, log)
