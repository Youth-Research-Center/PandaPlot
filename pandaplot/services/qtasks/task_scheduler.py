import logging
from typing import Any, Callable, Optional, Tuple

from PySide6.QtCore import QThreadPool

from pandaplot.services.qtasks.worker import Worker, WorkerFuncType


class TaskScheduler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        self.threadpool = QThreadPool()
        thread_count = self.threadpool.maxThreadCount()
        self.logger.info(f"Multithreading with maximum {thread_count} threads")

    def run_task(self, 
                 task: WorkerFuncType, 
                 task_arguments:dict, 
                 on_result:Optional[Callable[[Any], None]], 
                 on_error:Optional[Callable[[Tuple], None]], 
                 on_finished:Optional[Callable], 
                 on_progress:Optional[Callable[[float], None]]):
        worker = Worker(
            **task_arguments
        )  # Any other args, kwargs are passed to the run function
        if on_result:
            worker.signals.result.connect(on_result)
        if on_finished:
            worker.signals.finished.connect(on_finished)
        if on_progress:
            worker.signals.progress.connect(on_progress)
        if on_error:
            worker.signals.error.connect(on_error)

        # Execute
        self.threadpool.start(worker)