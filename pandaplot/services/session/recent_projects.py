"""Recent projects lookup.

Shared by WelcomeTab (recent-projects cards) and MainMenu (File > Recent
submenu) so both consumers see the same filtering/sorting rules.
"""
from __future__ import annotations

import datetime
import logging
import os
from pathlib import Path

from pandaplot.models.state.app_context import AppContext
from pandaplot.services.config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


def get_recent_projects(app_context: AppContext) -> list[dict]:
    """Return a list of recent projects from app configuration.

    Reads ConfigManager.config.recent_projects, filters to paths that still
    exist on disk, and derives a display name (file stem) and last_opened
    (file mtime) for each. Sorted newest-first.

    Each returned entry is dict: { name, path, last_opened }
    """
    try:
        if not app_context:
            return []
        cfg_manager = app_context.get_manager(ConfigManager)
        cfg = cfg_manager.config
        if not cfg:
            return []
        recent_paths = cfg.recent_projects
        if not recent_paths:
            return []
        results = []
        for p in recent_paths:
            if not p:
                continue
            try:
                path_obj = Path(p)
                if not path_obj.exists():
                    continue
                name = path_obj.stem
                # Use file modified time as last_opened fallback
                ts = os.path.getmtime(p)
                last_opened = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                results.append({
                    "name": name,
                    "path": str(path_obj),
                    "last_opened": last_opened
                })
            except Exception:
                continue
        # Sort newest first by last_opened timestamp string descending
        results.sort(key=lambda x: x["last_opened"], reverse=True)
        return results
    except Exception as e:
        logger.warning("Failed to load recent projects: %s", e)
        return []


__all__ = ["get_recent_projects"]
