import subprocess
import sys


def test_tab_container_does_not_import_matplotlib_or_markdown_eagerly():
    """ChartTab pulls the matplotlib Qt backend (~0.5s) and NoteTab pulls markdown.
    Neither may load until a chart/note tab is actually opened."""
    code = (
        "import sys; "
        "import pandaplot.gui.components.tabs.tab_container; "
        "assert 'matplotlib' not in sys.modules, 'matplotlib was imported eagerly'; "
        "assert 'markdown' not in sys.modules, 'markdown was imported eagerly'"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
