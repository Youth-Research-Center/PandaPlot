"""Applying the application theme must not let the cyclic GC free widgets mid-repolish.

``QApplication.setStyleSheet`` works from a snapshot of every styled widget and sends each one a ``StyleChange`` event,
which runs Python ``changeEvent`` overrides. If an automatic GC pass starts inside one of those callbacks and frees a
parentless widget that is already in the snapshot, Qt touches a dangling pointer and the process dies with a
segmentation fault (seen rarely in CI during ``app_window`` fixture setup, issue #648). Whether the use-after-free
crashes depends on heap layout, so these tests pin the contract that removes it instead of provoking the crash:
the Qt calls run with the automatic collector paused.
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.models.state.config import Theme
from pandaplot.services.theme.theme_manager import ThemeContext, ThemeManager
from pandaplot.utils.garbage_collection import paused_garbage_collection


class RecordingApplication:
    """Forwards to the real QApplication and records whether the automatic GC was enabled at each call."""

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self.gc_enabled_during: dict[str, bool] = {}

    def __getattr__(self, name: str):
        return getattr(self._app, name)

    def setPalette(self, palette) -> None:
        self.gc_enabled_during["setPalette"] = gc.isenabled()
        self._app.setPalette(palette)

    def setStyleSheet(self, stylesheet: str) -> None:
        self.gc_enabled_during["setStyleSheet"] = gc.isenabled()
        self._app.setStyleSheet(stylesheet)

    def setFont(self, font) -> None:
        self.gc_enabled_during["setFont"] = gc.isenabled()
        self._app.setFont(font)


@pytest.fixture
def restored_application(qapp: QApplication):
    palette, font, stylesheet = qapp.palette(), qapp.font(), qapp.styleSheet()
    try:
        yield qapp
    finally:
        qapp.setStyleSheet(stylesheet)
        qapp.setPalette(palette)
        qapp.setFont(font)


def _manager_for(application, theme: Theme) -> ThemeManager:
    manager = ThemeManager.__new__(ThemeManager)
    manager._app = application
    manager._current = ThemeContext(theme=theme, accent="#4A56C6", interface_font_size=10)
    return manager


def test_apply_to_qapp_runs_every_application_wide_qt_call_with_the_gc_paused(restored_application: QApplication) -> None:
    recorder = RecordingApplication(restored_application)
    manager = _manager_for(recorder, Theme.DARK)
    assert gc.isenabled()

    manager._apply_to_qapp(manager._current)

    assert recorder.gc_enabled_during == {"setPalette": False, "setStyleSheet": False, "setFont": False}
    assert gc.isenabled()
    assert restored_application.styleSheet() == manager.build_stylesheet(manager._current)


def test_apply_to_qapp_restores_the_gc_when_applying_fails(restored_application: QApplication) -> None:
    class FailingApplication(RecordingApplication):
        def setStyleSheet(self, stylesheet: str) -> None:
            raise RuntimeError("stylesheet rejected")

    manager = _manager_for(FailingApplication(restored_application), Theme.LIGHT)

    with pytest.raises(RuntimeError, match="stylesheet rejected"):
        manager._apply_to_qapp(manager._current)

    assert gc.isenabled()


def test_paused_garbage_collection_disables_gc_only_inside_the_block() -> None:
    assert gc.isenabled()

    with paused_garbage_collection():
        assert not gc.isenabled()

    assert gc.isenabled()


def test_paused_garbage_collection_restores_gc_when_the_block_raises() -> None:
    with pytest.raises(RuntimeError), paused_garbage_collection():
        raise RuntimeError("boom")

    assert gc.isenabled()


def test_paused_garbage_collection_leaves_gc_disabled_when_it_already_was() -> None:
    gc.disable()
    try:
        with paused_garbage_collection():
            assert not gc.isenabled()

        assert not gc.isenabled()
    finally:
        gc.enable()
