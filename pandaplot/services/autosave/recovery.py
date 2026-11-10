"""Recovery copy of an untitled project.

An untitled project (one with no file path) has nowhere to be auto-saved, so
the auto-save manager keeps a recovery copy in the app data folder next to the
config and session files. It is offered for restore on the next launch and
deleted as soon as there is nothing left to recover: after a Save As, an
explicit Discard, when the project is closed or replaced, and on a clean exit
with no modified untitled project. Dismissing the launch prompt keeps it.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

RECOVERY_FILE_NAME = "untitled-recovery.pplot"
# Keeps the project file suffix so ProjectManager accepts it; renamed over the recovery file once fully written.
RECOVERY_TEMP_FILE_NAME = "untitled-recovery.partial.pplot"


def recovery_file_path() -> Path:
    """Return the path of the untitled-project recovery copy (``~/.pandaplot/recovery``)."""
    return Path.home() / ".pandaplot" / "recovery" / RECOVERY_FILE_NAME


def recovery_temp_path() -> Path:
    """Return the temporary path a recovery copy is written to before it replaces the real one."""
    return recovery_file_path().with_name(RECOVERY_TEMP_FILE_NAME)


def delete_recovery_copy() -> None:
    """Delete the recovery copy and any half-written temporary file; a missing file is fine."""
    path = recovery_file_path()
    for candidate in (path, recovery_temp_path()):
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete recovery file %s", candidate, exc_info=True)


__all__ = ["RECOVERY_FILE_NAME", "RECOVERY_TEMP_FILE_NAME", "delete_recovery_copy", "recovery_file_path", "recovery_temp_path"]
