import subprocess
import sys


def test_analysis_engine_does_not_import_scipy_eagerly():
    """scipy costs ~2.5s at import; it must only load when an analysis runs."""
    code = (
        "import sys; "
        "import pandaplot.analysis.analysis_engine; "
        "assert 'scipy' not in sys.modules, 'scipy was imported eagerly'"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
