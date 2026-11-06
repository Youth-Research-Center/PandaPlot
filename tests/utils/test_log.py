"""Tests for setup_logging."""

import logging

import pytest

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


@pytest.fixture
def clean_root_logger():
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    root.handlers = []
    try:
        yield root
    finally:
        for handler in root.handlers[:]:
            handler.close()
        root.handlers = original_handlers
        root.setLevel(original_level)


def _file_handlers(root: logging.Logger) -> list[logging.FileHandler]:
    return [h for h in root.handlers if isinstance(h, logging.FileHandler)]


def test_setup_logging_closes_handlers_from_previous_call(tmp_path, clean_root_logger):
    root = clean_root_logger
    setup_logging(tmp_path / "first.log", cli_level=None)
    (first_handler,) = _file_handlers(root)
    assert first_handler.stream is not None

    setup_logging(tmp_path / "second.log", cli_level=None)

    assert first_handler not in root.handlers
    assert first_handler.stream is None
    (second_handler,) = _file_handlers(root)
    assert second_handler is not first_handler


def test_setup_logging_leaves_foreign_handlers_untouched(tmp_path, clean_root_logger):
    root = clean_root_logger
    foreign = _TrackingHandler()
    root.addHandler(foreign)

    setup_logging(tmp_path / "app.log", cli_level=None)
    setup_logging(tmp_path / "app.log", cli_level=None)

    assert foreign in root.handlers
    assert not foreign.closed
    assert len(_file_handlers(root)) == 1
