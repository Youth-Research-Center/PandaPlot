import logging
from typing import Any, Callable, Optional, Tuple, Union

from PySide6.QtCore import QMutex, QMutexLocker, QThreadPool

from pandaplot.services.qtasks.cancellation import CancellationToken
from pandaplot.services.qtasks.worker import Worker, WorkerFuncType

_RESERVED_TASK_ARGUMENT_KEYS = {"cancellation_token", "is_cancelled", "progress_callback"}


class TaskScheduler:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.threadpool = QThreadPool()
        thread_count = self.threadpool.maxThreadCount()
        self._workers = []
        self._workers_lock = QMutex()
        self.logger.info(f"Multithreading with maximum {thread_count} threads")

    def run_task(self, 
                 task: WorkerFuncType, 
                 task_arguments: Optional[dict] = None,
                 on_result: Optional[Callable[[Any], None]] = None,
                 on_error: Optional[Callable[[Tuple], None]] = None,
                 on_finished: Optional[Callable[[], None]] = None,
                 on_progress: Optional[Callable[[float], None]] = None,
                 on_cancelled: Optional[Callable[[], None]] = None,
                 cancellation_token: Optional[CancellationToken] = None) -> CancellationToken:
        task_arguments = task_arguments if task_arguments is not None else {}
        conflicting_keys = _RESERVED_TASK_ARGUMENT_KEYS & task_arguments.keys()
        if conflicting_keys:
            raise ValueError(
                f"task_arguments must not include reserved keys: {sorted(conflicting_keys)}"
            )
        token = cancellation_token or CancellationToken()

        worker = Worker(
            task,
            cancellation_token=token,
            **task_arguments
        )  # Any other args, kwargs are passed to the run function

        if on_result:
            worker.signals.result.connect(on_result)
        if on_progress:
            worker.signals.progress.connect(on_progress)
        if on_error:
            worker.signals.error.connect(on_error)
        if on_cancelled:
            worker.signals.cancelled.connect(on_cancelled)

        # Wrap finish so we both call user callback and clean up
        def _finished_wrapper():
            try:
                if on_finished:
                    on_finished()
            finally:
                # Disconnect all signals to release callback references (prevent memory leak).
                # Each disconnect is guarded individually so a failure on one does not
                # prevent the remaining signals from being disconnected.
                for name, signal, callback in [
                    ("result",    worker.signals.result,    on_result),
                    ("progress",  worker.signals.progress,  on_progress),
                    ("error",     worker.signals.error,     on_error),
                    ("cancelled", worker.signals.cancelled, on_cancelled),
                    ("finished",  worker.signals.finished,  _finished_wrapper),
                ]:
                    if callback is None:
                        continue
                    try:
                        signal.disconnect(callback)
                    except RuntimeError:
                        self.logger.debug("Signal '%s' already disconnected during worker cleanup.", name)

                # Remove reference after it has truly finished
                with QMutexLocker(self._workers_lock):
                    if worker in self._workers:
                        self._workers.remove(worker)
                        self.logger.debug("Removed worker successfully.")
                    else:
                        self.logger.warning("Worker not available in collection.")

        worker.signals.finished.connect(_finished_wrapper)
        with QMutexLocker(self._workers_lock):
            self._workers.append(worker)

        # Execute
        self.threadpool.start(worker)
        return token

    def cancel_task(self, task_or_token: Union[WorkerFuncType, CancellationToken]) -> bool:
        """Cancel task(s) by task function reference or cancellation token.

        Returns True if at least one matching worker token was cancelled.
        """
        cancelled_any = False
        with QMutexLocker(self._workers_lock):
            workers_copy = list(self._workers)

        for worker in workers_copy:
            if worker.cancellation_token == task_or_token or worker.fn == task_or_token:
                worker.cancellation_token.cancel()
                cancelled_any = True

        return cancelled_any

    def cancel_all(self) -> None:
        """Cancel all currently tracked worker tasks."""
        with QMutexLocker(self._workers_lock):
            workers_copy = list(self._workers)

        for worker in workers_copy:
            worker.cancellation_token.cancel()
