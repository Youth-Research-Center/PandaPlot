import os
from pathlib import Path

import pytest

# Registers the crash-safe xdist scheduler on the controller (`pytest_plugins` is not allowed here).
from tests.xdist_crash_safe import pytest_xdist_make_scheduler  # noqa: F401

# Must run before any PySide6/QApplication import so Qt never opens a real window.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolated_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Give every test its own empty home directory.

    ``ConfigManager`` and the application log default to ``~/.pandaplot``, so a test
    that builds an ``AppContext`` would otherwise read the developer's real settings,
    could overwrite them, and would race with other pytest-xdist workers on them.
    ``Path.home()`` reads ``HOME`` on POSIX and ``USERPROFILE`` on Windows, so both are
    redirected (child processes inherit them too). The directory is separate from
    ``tmp_path`` so tests that inspect ``tmp_path`` do not see a ``.pandaplot`` folder.

    Returns:
        The isolated home directory.
    """
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home
