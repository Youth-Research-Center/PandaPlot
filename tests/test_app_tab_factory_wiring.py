"""Tests that pandaplot.app registers a usable TabFactory."""

from pandaplot.app import create_tab_factory
from pandaplot.gui.components.tabs.tab_factory import TabFactory
from pandaplot.models.project.items import Chart, Dataset, ImageGallery, Note


def test_create_tab_factory_registers_all_four_tab_item_types():
    factory = create_tab_factory()

    assert isinstance(factory, TabFactory)
    assert set(factory._registry.keys()) == {Note, Chart, Dataset, ImageGallery}


def test_create_tab_factory_does_not_import_tab_modules_eagerly():
    import subprocess
    import sys

    code = (
        "import sys; "
        "from pandaplot.app import create_tab_factory; "
        "create_tab_factory(); "
        "assert 'matplotlib' not in sys.modules, 'matplotlib was imported eagerly'; "
        "assert 'markdown' not in sys.modules, 'markdown was imported eagerly'"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_build_app_context_applies_and_tracks_undo_depth_config(tmp_path, monkeypatch):
    from pandaplot.app import build_app_context
    from pandaplot.commands.command_executor import CommandExecutor
    from pandaplot.services.config.config_manager import ConfigManager

    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_app_context()
    executor = context.get_manager(CommandExecutor)
    config = context.get_manager(ConfigManager)
    assert executor.max_undo_levels == config.config.max_undo_levels == 10

    config.update({"max_undo_levels": 23}, save=False)
    assert executor.max_undo_levels == 23
