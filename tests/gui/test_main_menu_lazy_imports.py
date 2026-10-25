import subprocess
import sys


def test_main_menu_does_not_import_matplotlib_or_scipy_eagerly():
    """main_menu transitively imports commands/models (pandas is expected and allowed);
    matplotlib (via AboutDialog) and scipy (via analysis commands) must stay lazy."""
    code = (
        "import sys; "
        "import pandaplot.gui.components.main_menu.main_menu; "
        "assert 'matplotlib' not in sys.modules, 'matplotlib was imported eagerly'; "
        "assert 'scipy' not in sys.modules, 'scipy was imported eagerly'"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
