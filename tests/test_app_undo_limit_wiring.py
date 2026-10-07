"""build_app_context keeps the CommandExecutor's undo limit in sync with config."""
from __future__ import annotations

from pathlib import Path

import pytest

from pandaplot.app import build_app_context
from pandaplot.services.config.config_manager import ConfigManager


@pytest.fixture
def app_context(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return build_app_context()


def test_executor_starts_with_configured_undo_limit(app_context):
    config_manager = app_context.get_manager(ConfigManager)
    executor = app_context.get_command_executor()

    assert executor.max_undo_levels == config_manager.config.max_undo_levels == 10


def test_config_update_changes_executor_undo_limit(app_context):
    config_manager = app_context.get_manager(ConfigManager)
    executor = app_context.get_command_executor()

    config_manager.update({"max_undo_levels": 50})

    assert executor.max_undo_levels == 50


def test_config_reset_restores_executor_undo_limit(app_context):
    config_manager = app_context.get_manager(ConfigManager)
    executor = app_context.get_command_executor()
    config_manager.update({"max_undo_levels": 50})

    config_manager.reset()

    assert executor.max_undo_levels == 10
