"""Auto-save manager.

Periodically saves the currently loaded project to disk so in-progress work
survives a crash or an accidental quit. Driven by ``ApplicationConfig.auto_save``
(``enabled`` + ``interval_seconds``, already exposed in Settings) and reacts
live if those settings change.

Only projects that already have a file path are auto-saved - a brand new,
never-saved project has nowhere to write to, and prompting a blocking
"Save As" dialog from a background timer would be jarring.
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QTimer

from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.events.event_types import ConfigEvents
from pandaplot.models.state.app_state import AppState
from pandaplot.models.state.config import AutoSaveConfig
from pandaplot.services.config.config_manager import ConfigManager


class AutoSaveManager:
    """Periodically saves the current project in the background."""

    def __init__(self, event_bus: EventBus, config_manager: ConfigManager, app_state: AppState):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._config_manager = config_manager
        self._app_state = app_state
        # Needed to construct SaveProjectCommand; injected once the AppContext
        # that owns this manager finishes building (see set_app_context()).
        self._app_context = None

        self._timer: Optional[QTimer] = None
        self._current_save = None  # in-flight SaveProjectCommand, if any

        event_bus.subscribe(ConfigEvents.CONFIG_UPDATED, self._on_config_updated)
        from pandaplot.models.events.event_types import AppEvents
        event_bus.subscribe(AppEvents.APP_CLOSING, self._on_app_closing)

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

        # Never-saved project: skip rather than trigger a blocking Save As dialog.
        if not self._app_state.project_file_path:
            return

        # Avoid overlapping saves: SaveProjectCommand.is_saving is only cleared
        # once its background task truly finishes (unlike execute(), which
        # returns as soon as the task is dispatched).
        if self._current_save is not None and self._current_save.is_saving:
            self._logger.debug("Skipping auto-save tick: previous auto-save still in progress")
            return

        from pandaplot.commands.project.project.save_project_command import SaveProjectCommand

        self._logger.debug("Auto-saving project '%s'", project.name)
        self._current_save = SaveProjectCommand(self._app_context)
        try:
            self._app_context.get_command_executor().execute_command(self._current_save, track_undo=False)
        except Exception:
            self._logger.exception("Auto-save failed")


__all__ = ["AutoSaveManager"]
