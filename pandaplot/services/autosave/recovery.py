"""Recovery copies of untitled projects.

An untitled project (one with no file path) has nowhere to be auto-saved, so
the auto-save manager keeps a recovery copy of it in ``~/.pandaplot/recovery``.
Each running PandaPlot writes its own copy, ``untitled-<session id>.pplot``,
and holds a ``QLockFile`` next to it for as long as it runs. A session only
ever deletes its own copy, so a second instance, or this session's own cleanup
(a Save As, Discard, closing or replacing the project, a clean quit), never
removes a copy that another session wrote.

A copy whose lock is not held by a running process was left by a session that
crashed or quit with unsaved untitled changes; it is *pending* and offered for
restore on the next launch (see ``claim_pending_recovery_copy``). Restoring
adopts it as this session's copy; Discard deletes it; dismissing the offer
leaves it for the next launch.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from PySide6.QtCore import QLockFile

logger = logging.getLogger(__name__)

_COPY_PREFIX = "untitled-"
# Keeps the project file suffix so ProjectManager accepts the files.
_COPY_SUFFIX = ".pplot"
_PARTIAL_SUFFIX = ".partial.pplot"
_LOCK_SUFFIX = ".lock"

SESSION_ID = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
"""Identifies this process's recovery copy."""

# (lock path, lock) held for this session's copy; re-created if the home folder changes (tests).
_session_lock: tuple[Path, QLockFile] | None = None
# Advanced by every deletion of this session's copy, so a background write that was
# already running when the copy was deleted can tell its result is stale.
_session_copy_generation = 0


def recovery_dir() -> Path:
    """Return the folder that holds recovery copies (``~/.pandaplot/recovery``)."""
    return Path.home() / ".pandaplot" / "recovery"


def session_recovery_path() -> Path:
    """Return the path of this session's recovery copy."""
    return recovery_dir() / f"{_COPY_PREFIX}{SESSION_ID}{_COPY_SUFFIX}"


def session_recovery_temp_path() -> Path:
    """Return the temporary path this session's copy is written to before it replaces the real one."""
    return recovery_dir() / f"{_COPY_PREFIX}{SESSION_ID}{_PARTIAL_SUFFIX}"


def _lock_path(copy_path: Path) -> Path:
    return copy_path.with_name(copy_path.name.removesuffix(_COPY_SUFFIX) + _LOCK_SUFFIX)


def _new_lock(copy_path: Path) -> QLockFile:
    lock = QLockFile(str(_lock_path(copy_path)))
    # Only a dead owner makes a lock stale: a long-running instance must keep its copy.
    lock.setStaleLockTime(0)
    return lock


def hold_session_lock() -> bool:
    """Lock this session's recovery copy so no other instance offers or deletes it.

    Idempotent; the lock is held until the process exits.

    Returns:
        True when this session holds the lock.
    """
    global _session_lock
    lock_path = _lock_path(session_recovery_path())
    if _session_lock is not None and _session_lock[0] == lock_path:
        return True
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.warning("Could not create the recovery folder %s", lock_path.parent, exc_info=True)
        return False
    lock = _new_lock(session_recovery_path())
    if not lock.tryLock(0):
        logger.warning("Could not lock this session's recovery copy (%s)", lock.error())
        return False
    if _session_lock is not None:
        _session_lock[1].unlock()
    _session_lock = (lock_path, lock)
    return True


def session_copy_generation() -> int:
    """Return a number that changes every time this session's recovery copy is deleted."""
    return _session_copy_generation


def delete_session_recovery_copy() -> None:
    """Delete this session's recovery copy and any half-written temporary file; a missing file is fine.

    Also advances ``session_copy_generation()``, so a recovery write still running in the
    background drops its result instead of recreating the deleted copy.
    """
    global _session_copy_generation
    _session_copy_generation += 1
    for candidate in (session_recovery_path(), session_recovery_temp_path()):
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete recovery file %s", candidate, exc_info=True)


class PendingRecoveryCopy:
    """A recovery copy left by a session that is no longer running, locked by this session while it is offered."""

    def __init__(self, path: Path, lock: QLockFile):
        self.path = path
        self._lock = lock

    def adopt(self) -> None:
        """Make this copy this session's own copy (after it has been restored), then release its old lock."""
        try:
            if hold_session_lock():
                os.replace(self.path, session_recovery_path())
        except OSError:
            logger.warning("Could not adopt recovery copy %s", self.path, exc_info=True)
        finally:
            self.release()

    def discard(self) -> None:
        """Delete this copy, then release its lock."""
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete recovery file %s", self.path, exc_info=True)
        finally:
            self.release()

    def release(self) -> None:
        """Release the lock without touching the copy, so it is offered again on the next launch."""
        self._lock.unlock()


def claim_pending_recovery_copy() -> PendingRecoveryCopy | None:
    """Lock and return the newest recovery copy whose session is no longer running.

    Copies held by a running instance (including this one) are skipped. Older pending
    copies stay on disk and are offered on later launches.

    Returns:
        The claimed copy, or None when there is none. The caller must ``adopt()``,
        ``discard()`` or ``release()`` it.
    """
    folder = recovery_dir()
    if not folder.is_dir():
        return None
    own = session_recovery_path()
    candidates = [
        path for path in folder.glob(f"{_COPY_PREFIX}*{_COPY_SUFFIX}")
        if not path.name.endswith(_PARTIAL_SUFFIX) and path != own and path.is_file()
    ]
    for path in sorted(candidates, key=_mtime, reverse=True):
        lock = _new_lock(path)
        if lock.tryLock(0):
            if path.is_file():
                return PendingRecoveryCopy(path, lock)
            lock.unlock()
    return None


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


__all__ = [
    "SESSION_ID",
    "PendingRecoveryCopy",
    "claim_pending_recovery_copy",
    "delete_session_recovery_copy",
    "hold_session_lock",
    "recovery_dir",
    "session_copy_generation",
    "session_recovery_path",
    "session_recovery_temp_path",
]
