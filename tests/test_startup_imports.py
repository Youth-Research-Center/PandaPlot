import subprocess
import sys

HEAVY_MODULES = ["scipy", "matplotlib", "markdown", "statsmodels", "openpyxl"]


def test_app_import_does_not_pull_heavy_optional_modules():
    """Startup budget guard: `import pandaplot.app` may pull PySide6 and pandas
    (core to the data model), but analysis/plotting/export libs must stay lazy.
    Baseline 2026-07-18: this cut import time from ~5.7s to ~2s."""
    checks = "; ".join(
        f"assert '{m}' not in sys.modules, '{m} was imported at startup'" for m in HEAVY_MODULES
    )
    code = f"import sys; import pandaplot.app; {checks}"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
