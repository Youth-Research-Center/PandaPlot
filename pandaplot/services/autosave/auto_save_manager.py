"""Auto-save manager.

Periodically saves the currently loaded project to disk so in-progress work
survives a crash or an accidental quit. Driven by ``ApplicationConfig.auto_save``
(``enabled`` + ``interval_seconds``, already exposed in Settings) and reacts
live if those settings change.

A project that already has a file path is saved in place. An untitled project
(a new project, or an opened example) has nowhere to write to and a blocking
"Save As" dialog from a timer would be jarring, so while it has unsaved changes
a recovery copy is written to the app data folder instead (see
``pandaplot.services.autosave.recovery``). The project itself is left untitled
and modified; the copy is offered for restore on the next launch. The copy is
deleted once there is nothing left to recover: when the project is saved to a
file, closed (which only happens after the unsaved-changes guard), or replaced
by another project. A project whose path is inside the bundled
examples folder is never written back to (#607).
"""
from __future__ import annotations

import logging
import os

from PySide6.QtCore import QTimer

from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.events.event_types import ConfigEvents, ProjectEvents
from pandaplot.models.state.app_state import AppState
from pandaplot.models.state.config import AutoSaveConfig
from pandaplot.services.autosave.recovery import delete_recovery_copy, recovery_file_path, recovery_temp_path
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

        event_bus.subscribe(ConfigEvents.CONFIG_UPDATED, self._on_config_updated)
        from pandaplot.models.events.event_types import AppEvents
        event_bus.subscribe(AppEvents.APP_CLOSING, self._on_app_closing)
        event_bus.subscribe(ProjectEvents.PROJECT_SAVED, self._on_project_saved)
        event_bus.subscribe(ProjectEvents.PROJECT_CLOSED, self._on_project_closed)
        event_bus.subscribe(ProjectEvents.PROJECT_LOADED, self._on_project_loaded)

    def _on_project_saved(self, event_data: dict) -> None:
        """An untitled project that was just given a file has nothing left to recover."""
        if not event_data.get("previous_path"):
            self._last_recovery_write = None
            delete_recovery_copy()

    def _on_project_closed(self, _event_data: dict) -> None:
        """A closed project was saved, discarded, or unmodified, so its recovery copy is stale."""
        self._last_recovery_write = None
        delete_recovery_copy()

    def _on_project_loaded(self, event_data: dict) -> None:
        """Replacing an untitled project (after the unsaved-changes guard) makes its recovery copy stale.

        Loading the recovery copy itself never reaches this: it is only offered when no
        untitled project is open, and the restored project is marked modified, so the next
        tick writes a fresh copy.
        """
        previous = event_data.get("previous_project")
        if previous is not None and not previous.project_file_path:
            self._last_recovery_write = None
            delete_recovery_copy()

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

    def _write_recovery_copy(self, project) -> None:
        """Write a recovery copy of a modified untitled project, leaving the project untouched.

        The copy is written to a temporary name and renamed over the previous
        copy, so a crash mid-write never destroys the last good copy. The
        project's file path and modified flag are not changed.
        """
        if not self._app_state.is_modified or self._app_state.is_saving:
            return
        stamp = (id(project), self._app_state.modification_revision)
        if stamp == self._last_recovery_write and recovery_file_path().exists():
            return

        from pandaplot.services.data_managers.project_manager import ProjectManager

        temp_path = recovery_temp_path()
        try:
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            self._app_context.get_manager(ProjectManager).save_project(project, str(temp_path))
            os.replace(temp_path, recovery_file_path())
        except Exception:
            self._logger.exception("Writing the recovery copy of '%s' failed", project.name)
            temp_path.unlink(missing_ok=True)
            return
        self._last_recovery_write = stamp
        self._logger.debug("Wrote recovery copy of untitled project '%s'", project.name)


__all__ = ["AutoSaveManager"]
