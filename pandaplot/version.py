"""Application version and metadata, sourced from pyproject.toml.

Reads directly from pyproject.toml rather than importlib.metadata since the
app is normally run from source (not installed as a package), so package
metadata isn't available. Falls back to hardcoded values if the file can't
be read (e.g. a future frozen/packaged build).
"""

import tomllib
from pathlib import Path

FALLBACK_NAME = "PandaPlot"
FALLBACK_VERSION = "0.1.0"
FALLBACK_DESCRIPTION = (
    "PandaPlot is educational scientific visualization and analysis application "
    "built with Python. The project is open source and welcomes contribution."
)


def _load_project_metadata() -> dict:
    try:
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {})
    except Exception:  # noqa: BLE001 -- Best-effort metadata read; falls back to an empty dict if pyproject.toml is missing/malformed
        return {}


_project = _load_project_metadata()

__version__ = _project.get("version", FALLBACK_VERSION)
__app_name__ = "PandaPlot"
__description__ = _project.get("description", FALLBACK_DESCRIPTION)
