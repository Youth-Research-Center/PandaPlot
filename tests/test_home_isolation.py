"""Every test runs against a throwaway home directory, never the developer's real one.

``ConfigManager`` and the application log default to ``~/.pandaplot``. Without an
isolated home, any test that builds an ``AppContext`` reads the developer's real
settings, can overwrite them, and races with other pytest-xdist workers on them.
"""

from pathlib import Path

from pandaplot.app import build_app_context
from pandaplot.models.events import EventBus
from pandaplot.services.config.config_manager import ConfigManager


def test_home_directory_is_redirected_into_the_pytest_temp_area(tmp_path_factory):
    assert Path.home().is_relative_to(tmp_path_factory.getbasetemp())


def test_each_test_starts_with_an_empty_home():
    assert list(Path.home().iterdir()) == []


def test_default_config_manager_uses_the_isolated_home(tmp_path_factory):
    config_manager = ConfigManager(EventBus())

    assert config_manager.path.is_relative_to(tmp_path_factory.getbasetemp())
    assert config_manager.path.parent == Path.home() / ".pandaplot"


def test_build_app_context_never_reads_or_writes_the_real_config(tmp_path_factory):
    context = build_app_context()

    config_manager = context.get_manager(ConfigManager)
    assert config_manager.path.is_relative_to(tmp_path_factory.getbasetemp())
    config_manager.save()
    assert config_manager.path.exists()


def test_a_test_that_writes_config_does_not_leak_into_the_next_one():
    ConfigManager(EventBus()).save()

    assert (Path.home() / ".pandaplot" / "config.json").exists()


def test_the_previous_tests_config_is_gone():
    assert not (Path.home() / ".pandaplot" / "config.json").exists()
