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
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
