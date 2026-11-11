"""Auto-save manager.

Periodically saves the currently loaded project to disk so in-progress work
survives a crash or an accidental quit. Driven by ``ApplicationConfig.auto_save``
(``enabled`` + ``interval_seconds``, already exposed in Settings) and reacts
live if those settings change.

A project that already has a file path is saved in place. An untitled project
(a new project, or an opened example) has nowhere to write to and a blocking
"Save As" dialog from a timer would be jarring, so while it has unsaved changes
this session's recovery copy is written to the app data folder instead, in the
background (see ``pandaplot.services.autosave.recovery``). The project itself is
left untitled and modified; if the session ends without saving it, the copy is
offered for restore on the next launch. This session's copy is deleted once
there is nothing left to recover: when the project is saved to a file, closed
(which only happens after the unsaved-changes guard), or replaced by another
project. Copies written by other sessions are never touched here. Recovery
copies are only written while Auto-Save is enabled, since this timer drives them. A project whose path is inside the bundled
examples folder is never written back to (#607).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtCore import QTimer

from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.events.event_types import ConfigEvents, ProjectEvents
from pandaplot.models.state.app_state import AppState
from pandaplot.models.state.config import AutoSaveConfig
from pandaplot.services.autosave.recovery import (
    delete_session_recovery_copy,
    hold_session_lock,
    session_copy_generation,
    session_recovery_path,
    session_recovery_temp_path,
)
from pandaplot.services.config.config_manager import ConfigManager
from pandaplot.utils.examples import is_in_examples_dir


class AutoSaveManager:
    """Periodically saves the current project in the background."""

    def __init__(self, event_bus: EventBus, config_manager: ConfigManager, app_state: AppState):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._config_manager = config_manager
        self._app_state = app_state
        # Needed to construct SaveProjectCommand; injected once the AppContext
        # that owns this manager finishes building (see set_app_context()).
        self._app_context = None

        self._timer: QTimer | None = None
        self._current_save = None  # in-flight SaveProjectCommand, if any
        # (id(project), modification_revision) of the last recovery copy written,
        # so an idle untitled project is not rewritten on every tick.
        self._last_recovery_write: tuple[int, int] | None = None
        # A background write that finds the copy deleted (session_copy_generation() changed) or
        # the project edited meanwhile drops its result instead of replacing the copy.
        self._recovery_write_in_flight = False

        event_bus.subscribe(ConfigEvents.CONFIG_UPDATED, self._on_config_updated)
        from pandaplot.models.events.event_types import AppEvents
        event_bus.subscribe(AppEvents.APP_CLOSING, self._on_app_closing)
        event_bus.subscribe(ProjectEvents.PROJECT_SAVED, self._on_project_saved)
        event_bus.subscribe(ProjectEvents.PROJECT_CLOSED, self._on_project_closed)
        event_bus.subscribe(ProjectEvents.PROJECT_LOADED, self._on_project_loaded)

    def _on_project_saved(self, event_data: dict) -> None:
        """An untitled project that was just given a file has nothing left to recover."""
        if not event_data.get("previous_path"):
            self._discard_session_copy()

    def _on_project_closed(self, _event_data: dict) -> None:
        """A closed project was saved, discarded, or unmodified, so its recovery copy is stale."""
        self._discard_session_copy()

    def _on_project_loaded(self, event_data: dict) -> None:
        """Replacing an untitled project (after the unsaved-changes guard) makes its recovery copy stale.

        Loading the recovery copy itself never reaches this: it is only offered when no
        untitled project is open, and the restored project is marked modified, so the next
        tick writes a fresh copy.
        """
        previous = event_data.get("previous_project")
        if previous is not None and not previous.project_file_path:
            self._discard_session_copy()

    def _on_app_closing(self, _event_data: dict) -> None:
        self.stop()

    def set_app_context(self, app_context) -> None:
        self._app_context = app_context
    def start(self) -> None:
        """Start the auto-save timer. Call once a QApplication exists."""
        if self._timer is None:
            self._timer = QTimer()
            self._timer.timeout.connect(self._on_timer)
        self._apply_config(self._config_manager.config.auto_save)

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()

    def _apply_config(self, auto_save_cfg: AutoSaveConfig) -> None:
        if self._timer is None:
            return
        if auto_save_cfg.enabled:
            interval_ms = max(auto_save_cfg.interval_seconds, 1) * 1000
            self._timer.start(interval_ms)
            self._logger.debug("Auto-save enabled, interval=%ss", auto_save_cfg.interval_seconds)
        else:
            self._timer.stop()
            self._logger.debug("Auto-save disabled")

    def _on_config_updated(self, event_data: dict) -> None:
        config = event_data.get("config")
        if config is not None:
            self._apply_config(config.auto_save)

    def _on_timer(self) -> None:
        if self._app_context is None:
            return
        if not self._app_state.has_project:
            return
        project = self._app_state.current_project
        if project is None:
            return

        # Never-saved project: keep a recovery copy instead of prompting for a path.
        if not self._app_state.project_file_path:
            self._write_recovery_copy(project)
            return
        # A bundled example is never written back to (#607); SaveProjectCommand would
        # instead open a Save dialog, which a timer must not do.
        if is_in_examples_dir(self._app_state.project_file_path):
            return

        # Avoid overlapping saves: SaveProjectCommand.is_saving is only cleared
        # once its background task truly finishes (unlike execute(), which
        # returns as soon as the task is dispatched). AppState.is_saving is
        # the same check but global -- it also catches a manual Save (or the
        # exit-time autosave in unsaved_changes.py) started from outside
        # this manager, which self._current_save alone can't see.
        if (self._current_save is not None and self._current_save.is_saving) or self._app_state.is_saving:
            self._logger.debug("Skipping auto-save tick: a save is already in progress")
            return

        from pandaplot.commands.project.project.save_project_command import SaveProjectCommand

        self._logger.debug("Auto-saving project '%s'", project.name)
        self._current_save = SaveProjectCommand(self._app_context)
        try:
            self._app_context.get_command_executor().execute_command(self._current_save, track_undo=False)
        except Exception:
            self._logger.exception("Auto-save failed")

    def _discard_session_copy(self) -> None:
        """Delete this session's recovery copy; a background write still running for it is dropped."""
        self._last_recovery_write = None
        delete_session_recovery_copy()

    def _write_recovery_copy(self, project) -> None:
        """Write this session's recovery copy of a modified untitled project in the background.

        The copy is written to a temporary name on a worker thread and renamed over
        the previous copy on the main thread, so a crash mid-write never destroys the
        last good copy and a copy that became stale meanwhile is not recreated. The
        project's file path and modified flag are not changed. A write is dropped, keeping
        the previous copy, when the copy is deleted meanwhile (Save As, Discard, close,
        replace) or when the project is edited while it is serialised, since such a copy
        may mix the states before and after the edit; the next tick writes it again.
        """
        if not self._app_state.is_modified or self._app_state.is_saving or self._recovery_write_in_flight:
            return
        stamp = (id(project), self._app_state.modification_revision)
        if stamp == self._last_recovery_write and session_recovery_path().exists():
            return
        if not hold_session_lock():
            self._logger.warning("Writing the recovery copy without holding its lock")

        generation = session_copy_generation()
        self._recovery_write_in_flight = True
        try:
            self._app_context.get_task_scheduler().run_task(
                task=self._write_recovery_task,
                task_arguments={"project": project, "temp_path": str(session_recovery_temp_path())},
                on_result=lambda result: self._on_recovery_written(result, project_name=project.name, stamp=stamp, generation=generation),
                on_error=lambda error_info: self._logger.error("Writing the recovery copy of '%s' failed: %s", project.name, error_info[1]),
                on_finished=self._on_recovery_write_finished,
            )
        except Exception:
            self._recovery_write_in_flight = False
            self._logger.exception("Could not start writing the recovery copy of '%s'", project.name)

    def _write_recovery_task(self, progress_callback, project, temp_path: str, **_kwargs) -> bool:
        """Serialise ``project`` to ``temp_path`` on a worker thread."""
        from pandaplot.services.data_managers.project_manager import ProjectManager

        Path(temp_path).parent.mkdir(parents=True, exist_ok=True)
        self._app_context.get_manager(ProjectManager).save_project(project, temp_path)
        return True

    def _on_recovery_written(self, _result: object, *, project_name: str, stamp: tuple[int, int], generation: int) -> None:
        temp_path = session_recovery_temp_path()
        if generation != session_copy_generation():
            # The copy was deleted (saved, discarded, closed, replaced) while it was being written.
            temp_path.unlink(missing_ok=True)
            return
        project_id, revision = stamp
        current = self._app_state.current_project
        if current is None or id(current) != project_id or self._app_state.modification_revision != revision:
            # Edited (or replaced) while being serialised: the file may be inconsistent. Keep the
            # previous copy; the next tick writes the current state.
            self._logger.debug("Dropping the recovery copy of '%s': the project changed while it was written", project_name)
            temp_path.unlink(missing_ok=True)
            return
        try:
            os.replace(temp_path, session_recovery_path())
        except OSError:
            self._logger.exception("Replacing the recovery copy of '%s' failed", project_name)
            temp_path.unlink(missing_ok=True)
            return
        self._last_recovery_write = stamp
        self._logger.debug("Wrote recovery copy of untitled project '%s'", project_name)

    def _on_recovery_write_finished(self) -> None:
        """Always runs after the write (after ``_on_recovery_written`` on success); drops a leftover partial file."""
        self._recovery_write_in_flight = False
        try:
            session_recovery_temp_path().unlink(missing_ok=True)
        except OSError:
            self._logger.warning("Could not delete the partial recovery copy", exc_info=True)


__all__ = ["AutoSaveManager"]
