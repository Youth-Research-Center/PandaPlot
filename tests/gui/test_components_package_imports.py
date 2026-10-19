"""Importing one GUI component must not load the rest of the GUI.

pandaplot.gui.components used to re-export the sidebar and the tab container,
so importing any leaf widget from it (the shared combo box, say) initialised
the whole sidebar, tabs and commands first. Commands import dialogs, and
dialogs import shared widgets, so that closed an import cycle that depended on
which module happened to be imported first.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_in_fresh_interpreter(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_importing_a_leaf_widget_does_not_load_the_sidebar_or_tabs():
    result = _run_in_fresh_interpreter(
        "import sys;"
        "import pandaplot.gui.components.common.drop_down_combo_box;"
        "loaded = [m for m in ('pandaplot.gui.components.sidebar', 'pandaplot.gui.components.tabs') if m in sys.modules];"
        "assert not loaded, loaded"
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "module",
    [
        "pandaplot.gui.components.common.drop_down_combo_box",
        "pandaplot.gui.dialogs",
        "pandaplot.gui.dialogs.settings_dialog",
        "pandaplot.gui.dialogs.dataset.new_dataset_dialog",
        "pandaplot.commands.project.dataset.create_empty_dataset_command",
        "pandaplot.gui.components.sidebar.sidebar",
        "pandaplot.gui.components.tabs.tab_container",
        "pandaplot.gui.main_window",
    ],
)
def test_module_imports_first_in_a_fresh_interpreter(module):
    result = _run_in_fresh_interpreter(f"import {module}")

    assert result.returncode == 0, result.stderr
