"""Test integration of ConfigManager into AppContext (Phase 1.3)."""
from __future__ import annotations

from pandaplot.models.state import (AppState, AppContext)
from pandaplot.models.events.event_bus import EventBus
from pandaplot.services.config import ConfigManager
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.storage.project_data_manager import ProjectDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory


def test_app_context_has_config_manager(tmp_path):
    event_bus = EventBus()
    project_data_manager = ProjectDataManager(ItemDataManagerFactory())
    app_state = AppState(event_bus, project_data_manager=project_data_manager)
    cfg_manager = ConfigManager(event_bus, config_path=tmp_path / "cfg.json")
    cfg_manager.load()
    theme_manager = ThemeManager(event_bus, cfg_manager, None)
    ctx = AppContext(app_state, event_bus, command_executor=None, ui_controller=None, config_manager=cfg_manager, theme_manager=theme_manager)  # type: ignore[arg-type]

    assert ctx.get_config_manager() is cfg_manager
    # Ensure version present
    assert ctx.get_config_manager().config.version  # noqa: PT018
