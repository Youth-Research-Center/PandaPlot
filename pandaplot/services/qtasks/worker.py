import sys
import traceback
from typing import Any, Callable, Optional, Protocol

from PySide6.QtCore import (
    QRunnable,
    Slot,
)

from pandaplot.services.qtasks.cancellation import (
    CancellationToken,
    TaskCancelledError,
    build_cancellation_kwargs,
)
from pandaplot.services.qtasks.worker_signal import WorkerSignals


class WorkerFuncType(Protocol):
    def __call__(self, progress_callback: Callable[[float], None], *args: Any, **kwargs: Any) -> Any: ...


class Worker(QRunnable):
    """Worker thread.

    Inherits from QRunnable to handle worker thread setup, signals and wrap-up.

    :param fn: The function callback to run on this worker thread.
    :param cancellation_token: Optional CancellationToken instance to track task cancellation.
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function
    """

    def __init__(self, fn: WorkerFuncType, *args, cancellation_token: Optional[CancellationToken] = None, **kwargs):
        super().__init__()
        self.fn = fn
        self.cancellation_token = cancellation_token or CancellationToken()
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add progress_callback
        self.kwargs["progress_callback"] = self.signals.progress.emit

        # Inspect fn signature to supply cancellation tokens if accepted or if **kwargs accepted
        self.kwargs.update(build_cancellation_kwargs(fn, self.cancellation_token))

    def _is_cancelled(self) -> bool:
        return self.cancellation_token is not None and self.cancellation_token.is_cancelled()

    @Slot()
    def run(self):
        if self._is_cancelled():
            self.signals.cancelled.emit()
            self.signals.finished.emit()
            return

        try:
            result = self.fn(*self.args, **self.kwargs)
            if self._is_cancelled():
                raise TaskCancelledError("Task was cancelled.")
        except TaskCancelledError:
            self.signals.cancelled.emit()
        except Exception:
            # Any exception other than TaskCancelledError is a genuine task
            # failure, even if cancellation happens to have been requested
            # around the same time - do not misreport it as a cancellation.
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
