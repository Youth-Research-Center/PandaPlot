import pytest
from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from pandaplot.gui.components.common.p_button import PButton


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_default_role_is_secondary():
    button = PButton("Cancel")
    assert button.property("secondary") is True
    assert button.property("primary") is False
    assert button.property("destructive") is False


def test_primary_role_sets_primary_property_only():
    button = PButton("Apply", role="primary")
    assert button.property("primary") is True
    assert button.property("secondary") is False
    assert button.property("destructive") is False


def test_destructive_role_sets_destructive_property_only():
    button = PButton("Remove", role="destructive")
    assert button.property("destructive") is True
    assert button.property("primary") is False
    assert button.property("secondary") is False


def test_icon_flag_sets_icon_property_and_defaults_role_to_secondary():
    button = PButton("\U0001f5d1", icon=True)
    assert button.property("iconButton") is True
    assert button.property("secondary") is True


def test_icon_flag_combines_with_destructive_role():
    button = PButton("\U0001f5d1", role="destructive", icon=True)
    assert button.property("iconButton") is True
    assert button.property("destructive") is True


def test_set_role_changes_role_at_runtime():
    button = PButton("Apply", role="primary")
    button.set_role("secondary")
    assert button.property("primary") is False
    assert button.property("secondary") is True


def test_button_text_is_preserved():
    button = PButton("Apply", role="primary")
    assert button.text() == "Apply"


def test_on_click_connects_handler():
    calls = []
    button = PButton("Apply", role="primary", on_click=lambda: calls.append(True))
    button.click()
    assert calls == [True]


def test_omitting_on_click_makes_no_connection():
    button = PButton("Apply", role="primary")
    button.click()  # must not raise with no handler attached


def test_enabled_false_disables_button_at_construction():
    button = PButton("Apply", role="primary", enabled=False)
    assert button.isEnabled() is False


def test_enabled_defaults_to_true():
    button = PButton("Apply", role="primary")
    assert button.isEnabled() is True


def test_on_click_and_enabled_false_compose():
    calls = []
    button = PButton("Fit", role="primary", on_click=lambda: calls.append(True), enabled=False)
    assert button.isEnabled() is False
    button.setEnabled(True)
    button.click()
    assert calls == [True]


def test_on_click_accepts_a_qt_signal():
    from PySide6.QtCore import QObject, Signal

    class _Emitter(QObject):
        fired = Signal()

    emitter = _Emitter()
    calls = []
    emitter.fired.connect(lambda: calls.append(True))
    button = PButton("Apply", role="primary", on_click=emitter.fired)
    button.click()
    assert calls == [True]


def _solid_icon(color: str) -> QIcon:
    pixmap = QPixmap(8, 8)
    pixmap.fill(QColor(color))
    return QIcon(pixmap)


def _icon_color(button: PButton) -> str:
    return button.icon().pixmap(8, 8).toImage().pixelColor(4, 4).name()


def _enter(button: PButton) -> None:
    QApplication.sendEvent(button, QEvent(QEvent.Type.Enter))


def _leave(button: PButton) -> None:
    QApplication.sendEvent(button, QEvent(QEvent.Type.Leave))


def test_hover_icon_replaces_the_icon_while_hovered_and_restores_it_after():
    button = PButton("Delete", role="destructive")
    button.setIcon(_solid_icon("#ff0000"))
    button.set_hover_icon(_solid_icon("#ffffff"))

    assert _icon_color(button) == "#ff0000"
    _enter(button)
    assert _icon_color(button) == "#ffffff"
    _leave(button)
    assert _icon_color(button) == "#ff0000"


def test_disabled_button_never_shows_the_hover_icon():
    button = PButton("Delete", role="destructive", enabled=False)
    button.setIcon(_solid_icon("#ff0000"))
    button.set_hover_icon(_solid_icon("#ffffff"))

    _enter(button)

    assert _icon_color(button) == "#ff0000"


def test_disabling_a_hovered_button_restores_the_normal_icon():
    button = PButton("Delete", role="destructive")
    button.setIcon(_solid_icon("#ff0000"))
    button.set_hover_icon(_solid_icon("#ffffff"))
    _enter(button)

    button.setEnabled(False)

    assert _icon_color(button) == "#ff0000"


def test_setting_a_new_icon_while_hovered_keeps_the_hover_icon_and_updates_the_normal_one():
    button = PButton("Delete", role="destructive")
    button.setIcon(_solid_icon("#ff0000"))
    button.set_hover_icon(_solid_icon("#ffffff"))
    _enter(button)

    button.setIcon(_solid_icon("#00ff00"))
    assert _icon_color(button) == "#ffffff"

    _leave(button)
    assert _icon_color(button) == "#00ff00"


def test_clearing_the_hover_icon_restores_the_normal_icon():
    button = PButton("Delete", role="destructive")
    button.setIcon(_solid_icon("#ff0000"))
    button.set_hover_icon(_solid_icon("#ffffff"))
    _enter(button)

    button.set_hover_icon(None)

    assert _icon_color(button) == "#ff0000"
    _enter(button)
    assert _icon_color(button) == "#ff0000"


def _count_layout_requests(host: QWidget, action) -> int:
    class _Counter(QObject):
        def __init__(self) -> None:
            super().__init__()
            self.count = 0

        def eventFilter(self, watched, event) -> bool:
            if event.type() == QEvent.Type.LayoutRequest:
                self.count += 1
            return False

    counter = _Counter()
    host.installEventFilter(counter)
    QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
    counter.count = 0
    action()
    QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
    host.removeEventFilter(counter)
    return counter.count


def test_button_without_hover_icon_never_calls_qabstractbutton_set_icon_on_hover_or_enable_changes(monkeypatch):
    button = PButton("Plain")
    button.setIcon(_solid_icon("#ff0000"))
    calls = []
    original = QPushButton.setIcon
    monkeypatch.setattr(QPushButton, "setIcon", lambda self, icon: (calls.append(icon), original(self, icon))[1])

    for _ in range(3):
        _enter(button)
        _leave(button)
        button.setEnabled(False)
        button.setEnabled(True)

    assert calls == []
    assert _icon_color(button) == "#ff0000"


def test_button_without_hover_icon_posts_no_extra_layout_requests_on_hover_cycles():
    host = QWidget()
    QVBoxLayout(host)
    button = PButton("Plain", parent=host)
    host.layout().addWidget(button)
    button.setIcon(_solid_icon("#ff0000"))
    host.show()

    def cycle() -> None:
        for _ in range(5):
            _enter(button)
            _leave(button)
            button.setEnabled(False)
            button.setEnabled(True)

    assert _count_layout_requests(host, cycle) == 0


def test_hover_icon_is_only_applied_to_the_button_when_it_actually_flips(monkeypatch):
    button = PButton("Delete", role="destructive")
    button.setIcon(_solid_icon("#ff0000"))
    button.set_hover_icon(_solid_icon("#ffffff"))
    calls = []
    original = QPushButton.setIcon
    monkeypatch.setattr(QPushButton, "setIcon", lambda self, icon: (calls.append(icon), original(self, icon))[1])

    _enter(button)
    _enter(button)
    assert len(calls) == 1
    _leave(button)
    _leave(button)
    assert len(calls) == 2
