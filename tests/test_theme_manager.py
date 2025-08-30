from pathlib import Path

from pandaplot.models.events.event_bus import EventBus
from pandaplot.services.config import ConfigManager
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.models.state.config import ApplicationConfig, Theme


class DummyFont:
    def __init__(self):
        self._pt = 10
    def setPointSize(self, pt):
        self._pt = pt

class DummyApp:
    """Minimal stub of QApplication for stylesheet & palette testing."""
    def __init__(self):
        from PySide6.QtGui import QPalette
        self._stylesheet = ""
        self._palette = QPalette()
        self._font = DummyFont()

    def palette(self):  # noqa: N802
        return self._palette

    def font(self):  # noqa: N802
        return self._font

    def setFont(self, f):  # noqa: N802
        self._font = f

    def setPalette(self, palette):  # noqa: N802
        self._palette = palette

    def setStyleSheet(self, qss):  # noqa: N802
        self._stylesheet = qss

    def styleSheet(self):
        return self._stylesheet


def make_config(theme: Theme = Theme.DARK, accent: str = "#4A90E2", font_size: int = 12):
    cfg = ApplicationConfig.default()
    cfg.appearance.theme = theme
    cfg.appearance.accent_color = accent
    cfg.appearance.interface_font_size = font_size
    return cfg


def test_theme_manager_emits_on_config_events(tmp_path: Path):
    bus = EventBus()
    cfg_path = tmp_path / "cfg.json"
    cm = ConfigManager(bus, config_path=cfg_path, auto_save=False)
    tm = ThemeManager(bus, cm)
    app = DummyApp()
    tm.set_qt_app(app)

    emitted = []
    bus.subscribe("theme.changed", lambda d: emitted.append(d))

    # Trigger load event
    cm.load()
    assert emitted, "Theme change should occur on initial config load"
    emitted.clear()

    # Update config theme and ensure theme.changed fires
    cm.update({"appearance": {"theme": "light"}}, save=False)
    assert emitted, "Theme change should emit after config update"
    assert emitted[-1]["theme"] == Theme.LIGHT


def test_stylesheet_contains_accent_and_font(tmp_path: Path):
    bus = EventBus()
    cm = ConfigManager(bus, config_path=tmp_path / "c.json", auto_save=False)
    tm = ThemeManager(bus, cm)
    app = DummyApp()
    tm.set_qt_app(app)

    # Set explicit config values and apply
    cm.update({"appearance": {"accent_color": "#FF0000", "interface_font_size": 15}}, save=False)

    qss = app.styleSheet()
    assert "#FF0000" in qss
    # Font size applied to QApp font, not stylesheet
    assert app.font()._pt == 15


def test_idempotent_apply(tmp_path: Path):
    bus = EventBus()
    cm = ConfigManager(bus, config_path=tmp_path / "c.json", auto_save=False)
    tm = ThemeManager(bus, cm)
    app = DummyApp()
    tm.set_qt_app(app)

    cm.update({"appearance": {"theme": "dark"}}, save=False)
    first_qss = app.styleSheet()
    cm.update({"appearance": {"theme": "dark"}}, save=False)
    second_qss = app.styleSheet()
    assert first_qss == second_qss, "Applying same theme twice should produce same stylesheet"
