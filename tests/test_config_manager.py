"""Tests for ConfigManager service (Phase 1.2)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.state.config import ApplicationConfig, Theme
from pandaplot.services.config import ConfigManager


class EventCollector:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []

    def __call__(self, data: Dict[str, Any]):  # signature expected by bus
        self.events.append(data)


def test_load_default_when_missing(tmp_path: Path):
    bus = EventBus()
    manager = ConfigManager(bus, config_path=tmp_path / "config.json")
    collector = EventCollector()
    bus.subscribe("config.*", collector)

    cfg = manager.load()
    assert isinstance(cfg, ApplicationConfig)
    # Expect config.loaded event
    assert any(e.get("event_type") == "config.loaded" for e in collector.events)


def test_save_and_reload(tmp_path: Path):
    bus = EventBus()
    path = tmp_path / "settings.json"
    manager = ConfigManager(bus, config_path=path)
    manager.load()
    manager.update({"appearance": {"theme": "dark"}}, save=True)
    assert path.exists()

    # Recreate manager to ensure persisted
    bus2 = EventBus()
    manager2 = ConfigManager(bus2, config_path=path)
    cfg2 = manager2.load()
    assert cfg2.appearance.theme == Theme.DARK


def test_update_emits_changes(tmp_path: Path):
    bus = EventBus()
    manager = ConfigManager(bus, config_path=tmp_path / "c.json")
    manager.load()
    events: List[Dict[str, Any]] = []
    bus.subscribe("config.updated", lambda d: events.append(d))

    manager.update({"editor": {"tab_size": 8}}, save=False)
    assert events, "No update event captured"
    diff_entries = events[-1]["changes"]
    # Confirm diff path exists & shows change
    assert any(path.endswith("tab_size") for path in diff_entries.keys())


def test_reset_emits_reset_and_updated(tmp_path: Path):
    bus = EventBus()
    manager = ConfigManager(bus, config_path=tmp_path / "c.json")
    manager.load()
    reset_events: List[str] = []
    bus.subscribe("config.*", lambda d: reset_events.append(d["event_type"]))

    manager.update({"editor": {"tab_size": 6}})
    manager.reset(save=False)
    # Ensure both reset and updated appear
    assert "config.reset" in reset_events
    assert any(e == "config.updated" for e in reset_events)


def test_no_crash_on_corrupt_file(tmp_path: Path):
    bus = EventBus()
    path = tmp_path / "conf.json"
    path.write_text("{not valid")
    manager = ConfigManager(bus, config_path=path)
    cfg = manager.load()
    assert isinstance(cfg, ApplicationConfig)


def test_backup_created(tmp_path: Path):
    bus = EventBus()
    path = tmp_path / "conf.json"
    manager = ConfigManager(bus, config_path=path)
    manager.load()
    manager.update({"appearance": {"theme": "dark"}})
    manager.save()
    # Save again triggers backup creation
    manager.update({"appearance": {"accent_color": "#FFFFFF"}})
    manager.save()
    backup = path.with_suffix(path.suffix + ".bak")
    assert backup.exists()
