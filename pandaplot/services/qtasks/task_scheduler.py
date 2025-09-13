import logging
from typing import Any, Callable, Optional, Tuple

from PySide6.QtCore import QThreadPool

from pandaplot.services.qtasks.worker import Worker, WorkerFuncType


class TaskScheduler:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.threadpool = QThreadPool()
        thread_count = self.threadpool.maxThreadCount()
        self._workers = []
        self.logger.info(f"Multithreading with maximum {thread_count} threads")

    def run_task(self, 
                 task: WorkerFuncType, 
                 task_arguments:Optional[dict] = None, 
                 on_result:Optional[Callable[[Any], None]]=None, 
                 on_error:Optional[Callable[[Tuple], None]]=None, 
                 on_finished:Optional[Callable] =None, 
                 on_progress:Optional[Callable[[float], None]]=None):
        task_arguments = task_arguments if task_arguments is not None else {}
        
        worker = Worker(
            task,
            **task_arguments
        )  # Any other args, kwargs are passed to the run function

        if on_result:
            worker.signals.result.connect(on_result)
        if on_progress:
            worker.signals.progress.connect(on_progress)
        if on_error:
            worker.signals.error.connect(on_error)

        # Wrap finish so we both call user callback and clean up
        def _finished_wrapper():
            try:
                if on_finished:
                    on_finished()
            finally:
                # Remove reference after it has truly finished
                if worker in self._workers:
                    self._workers.remove(worker)
                    self.logger.debug("Removed worker successfully.")
                else:
                    self.logger.warning("Worker not available in collection.")
                

        worker.signals.finished.connect(_finished_wrapper)
        self._workers.append(worker)

        # Execute
        self.threadpool.start(worker)