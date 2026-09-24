"""Session Persistence Manager.

Remembers what was open (the current project, its open tabs/panes, and which
tab was active) so the app can restore it on the next launch. Owns the mapping
between session concepts and the underlying ApplicationConfig fields, so
callers never need to know the config's raw dict shape - they call
``update_project``/``update_tabs``/``reset`` instead of building a mapping
and calling ``ConfigManager.update()`` directly.
"""
from __future__ import annotations

from pandaplot.services.config.config_manager import ConfigManager


class SessionPersistenceManager:
    """Persists and restores "what was open" across app launches."""

    def __init__(self, config_manager: ConfigManager):
        self._config_manager = config_manager

    # ----- reading back the remembered session ------------------------------
    @property
    def last_project_path(self) -> str | None:
        return self._config_manager.config.last_project_path

    @property
    def last_tab_panes(self) -> list[list[str]]:
        """One entry per tab pane, each an ordered list of item ids."""
        return [list(pane) for pane in self._config_manager.config.last_tab_panes]

    @property
    def last_active_tab_id(self) -> str | None:
        return self._config_manager.config.last_active_tab_id

    @property
    def last_splitter_sizes(self) -> list[int]:
        return list(self._config_manager.config.last_splitter_sizes)

    # ----- recording session changes -----------------------------------------
    def update_project(self, file_path: str | None) -> None:
        """Remember which project to reopen on next launch (None to forget)."""
        self._config_manager.update({"last_project_path": file_path}, save=True)

    def update_tabs(
        self,
        panes: list[list[str]],
        active_tab_id: str | None,
        splitter_sizes: list[int] | None = None,
    ) -> None:
        """Remember which tabs were open in which pane, which was active, and
        (best-effort) the pane sizes, for next launch."""
        self._config_manager.update({
            "last_tab_panes": [list(pane) for pane in panes],
            "last_active_tab_id": active_tab_id,
            "last_splitter_sizes": list(splitter_sizes) if splitter_sizes else [],
        }, save=True)

    def reset(self) -> None:
        """Forget the remembered project and tabs (e.g. on explicit project close)."""
        self._config_manager.update({
            "last_project_path": None,
            "last_tab_panes": [],
            "last_active_tab_id": None,
            "last_splitter_sizes": [],
        }, save=True)


__all__ = ["SessionPersistenceManager"]
