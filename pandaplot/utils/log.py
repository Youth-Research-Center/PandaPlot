import logging
import sys
from pathlib import Path

# Handlers installed by the previous setup_logging() call. Only these are
# replaced on a repeat call, so handlers owned by someone else (a test
# harness, an embedding application) are never closed or removed.
_installed_handlers: list[logging.Handler] = []


def setup_logging(
    log_file: str | Path = "application.log",
    level: int = logging.INFO,
    cli_level: int | None = logging.INFO,
    file_level: int | None = logging.DEBUG,
    datefmt: str = "%Y-%m-%d %H:%M:%S"
):
    """
    Sets up logging for a PySide6 application to both file and CLI.

    Parameters
    ----------
    log_file : str | Path
        Path to the log file.
    level : int
        Minimum logging level for the root logger.
    cli_level : int
        Logging level for console output.
    file_level : int
        Logging level for file output.
    datefmt : str
        Format for timestamps in logs.
    """
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(level)

    # Prevent duplicate handlers if called multiple times, closing the ones
    # installed previously so their file handles are released.
    for handler in _installed_handlers:
        logger.removeHandler(handler)
        handler.close()
    _installed_handlers.clear()

    # Format: timestamp | level | logger name (module/class) | function | message
    log_format = "%(asctime)s | %(levelname)-5s | %(name)s | %(funcName)s | %(message)s"
    formatter = logging.Formatter(fmt=log_format, datefmt=datefmt)

    # File handler
    if file_level is not None:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        _installed_handlers.append(file_handler)

    # Console handler. StreamHandler() defaults to sys.stderr, which is None
    # in a windowed build with no attached console (e.g.
    # --windows-console-mode=disable), where it would raise on first write.
    if cli_level is not None and sys.stderr is not None:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(cli_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        _installed_handlers.append(console_handler)

    logger.debug("Logging initialized.")
    return logger