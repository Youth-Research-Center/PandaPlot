import subprocess
import sys


def test_fit_service_does_not_import_scipy_eagerly():
    code = (
        "import sys; "
        "import pandaplot.services.fit.fit_service; "
        "assert 'scipy' not in sys.modules, 'scipy was imported eagerly'"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
