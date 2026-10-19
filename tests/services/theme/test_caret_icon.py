import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

from pandaplot.services.theme.caret_icon import caret_icon_path

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def fresh_color(tmp_path, monkeypatch):
    """Point the cache at an empty directory so each test generates the file."""
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    return "#12AB34"


def test_caret_icon_is_written_and_uses_forward_slashes(fresh_color, tmp_path):
    path = caret_icon_path(fresh_color)

    assert os.sep == "/" or os.sep not in path
    assert os.path.exists(path)
    assert os.path.dirname(path) == str(tmp_path).replace(os.sep, "/")


def test_caret_icon_is_a_small_image_in_the_requested_colour(fresh_color):
    image = QImage(caret_icon_path(fresh_color))

    assert not image.isNull()
    assert (image.width(), image.height()) == (12, 12)
    # The caret's centre is solid; the corner is left transparent.
    centre = QColor(image.pixel(6, 6))
    assert centre.name() == fresh_color.lower()
    assert QColor.fromRgba(image.pixel(0, 0)).alpha() == 0


def test_caret_icon_is_cached_per_colour(fresh_color):
    first = caret_icon_path(fresh_color)
    modified = os.path.getmtime(first)

    assert caret_icon_path(fresh_color) == first
    assert os.path.getmtime(first) == modified
    assert caret_icon_path("#34AB12") != first


def test_caret_icon_does_not_need_a_gui_application(fresh_color, tmp_path):
    """A stylesheet can be built before any QGuiApplication exists (tests,
    start-up), which rules out QPixmap -- QImage must be used instead. Run in
    a subprocess because this process already has an application."""
    script = (
        "import sys, tempfile;"
        "tempfile.tempdir = sys.argv[1];"
        "from PySide6.QtGui import QGuiApplication;"
        "assert QGuiApplication.instance() is None;"
        "from pandaplot.services.theme.caret_icon import caret_icon_path;"
        "print(caret_icon_path('#0A0B0C'))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=REPO_ROOT,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert os.path.exists(result.stdout.strip())
