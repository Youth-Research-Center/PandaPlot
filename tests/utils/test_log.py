"""Tests for setup_logging."""

import logging

from pandaplot.utils.log import setup_logging


class _TrackingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    def emit(self, record: logging.LogRecord) -> None:
        pass

    def close(self) -> None:
        self.closed = True
        super().close()


def test_setup_logging_closes_replaced_handlers(tmp_path):
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    stale = _TrackingHandler()
    root.handlers = [stale]
    try:
        setup_logging(tmp_path / "app.log", cli_level=None)

        assert stale.closed
        assert stale not in root.handlers
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.FileHandler)
    finally:
        for handler in root.handlers[:]:
            handler.close()
        root.handlers = original_handlers
        root.setLevel(original_level)
