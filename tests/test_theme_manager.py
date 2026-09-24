from pathlib import Path

from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.state.config import ApplicationConfig, Theme
from pandaplot.services.config import ConfigManager
from pandaplot.services.theme.theme_manager import ThemeManager


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

    def palette(self):
        return self._palette

    def font(self):
        return self._font

    def setFont(self, f):
        self._font = f

    def setPalette(self, palette):
        self._palette = palette

    def setStyleSheet(self, qss):
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


def test_stylesheet_forces_readable_text_on_dialog_buttons(tmp_path: Path):
    """QMessageBox/QDialogButtonBox OK/Cancel buttons render via the native
    Windows visual-styles API on windowsvista/windows11 styles, which colors
    button labels from the OS theme and ignores QPalette entirely. Only an
    explicit QSS rule forces Qt's palette-aware fallback painter."""
    bus = EventBus()
    cm = ConfigManager(bus, config_path=tmp_path / "c.json", auto_save=False)
    tm = ThemeManager(bus, cm)
    app = DummyApp()
    tm.set_qt_app(app)

    cm.update({"appearance": {"theme": "light"}}, save=False)
    qss = app.styleSheet()

    assert "QMessageBox QPushButton" in qss
    assert "QDialogButtonBox QPushButton" in qss
    # Light theme's text_primary token, so the rule actually forces dark text.
    assert "#1C1E26" in qss


def test_palette_sets_all_roles_for_light_theme(tmp_path: Path):
    from PySide6.QtGui import QPalette

    bus = EventBus()
    cm = ConfigManager(bus, config_path=tmp_path / "c.json", auto_save=False)
    tm = ThemeManager(bus, cm)
    app = DummyApp()
    tm.set_qt_app(app)

    cm.update({"appearance": {"theme": "light"}}, save=False)

    palette = app.palette()
    fg = palette.color(QPalette.ColorRole.WindowText)
    bg = palette.color(QPalette.ColorRole.Window)

    # Roles that must follow the app's fg/bg choice rather than the
    # OS-inherited default palette (root cause of white-on-white text).
    assert palette.color(QPalette.ColorRole.Button) == bg
    assert palette.color(QPalette.ColorRole.ButtonText) == fg
    assert palette.color(QPalette.ColorRole.ToolTipBase) == bg
    assert palette.color(QPalette.ColorRole.ToolTipText) == fg
    placeholder = palette.color(QPalette.ColorRole.PlaceholderText)
    assert placeholder != bg
    assert placeholder != fg


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
