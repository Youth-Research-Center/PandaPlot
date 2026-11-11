"""Tests for UIController.show_save_as_discard_cancel and show_choice (#629).

QMessageBox.exec is replaced by a function that clicks the named button, so no modal loop runs.
"""
import sys
from collections.abc import Callable, Iterator

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from pandaplot.gui.controllers.ui_controller import UIController


def _click_on_exec(monkeypatch: pytest.MonkeyPatch, button_text: str | None) -> list[list[str]]:
    seen: list[list[str]] = []

    def fake_exec(box: QMessageBox) -> int:
        seen.append([button.text() for button in box.buttons()])
        for button in box.buttons():
            if button.text() == button_text:
                button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    return seen


@pytest.fixture
def controller() -> UIController:
    QApplication.instance() or QApplication(sys.argv)
    return UIController()


@pytest.mark.parametrize(
    ("clicked", "expected"),
    [("Save As...", "save_as"), ("Discard", "discard"), ("Cancel", "cancel"), (None, "cancel")],
)
def test_save_as_discard_cancel_returns_the_clicked_choice(
    controller: UIController, monkeypatch: pytest.MonkeyPatch, clicked: str | None, expected: str
) -> None:
    seen = _click_on_exec(monkeypatch, clicked)

    assert controller.show_save_as_discard_cancel("Unsaved Changes", "Message") == expected
    assert len(seen[0]) == 3
    assert {"Save As...", "Discard"} <= set(seen[0])


@pytest.mark.parametrize(("clicked", "expected"), [("Restore", True), ("Discard", False), ("Not Now", None), (None, None)])
def test_show_choice_distinguishes_each_button_from_dismissal(
    controller: UIController, monkeypatch: pytest.MonkeyPatch, clicked: str | None, *, expected: bool | None
) -> None:
    _click_on_exec(monkeypatch, clicked)

    assert controller.show_choice("Restore Project", "Message", "Restore", "Discard") is expected


@pytest.mark.parametrize("dismissal", ["reject", "close"])
def test_show_choice_returns_none_when_the_dialog_is_dismissed(
    controller: UIController, monkeypatch: pytest.MonkeyPatch, dismissal: str
) -> None:
    def fake_exec(box: QMessageBox) -> int:
        getattr(box, dismissal)()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)

    assert controller.show_choice("Restore Project", "Message", "Restore", "Discard") is None


class _ShownBoxDismisser:
    """Dismisses the next shown QMessageBox by a real Esc key press or a real close, from a timer.

    A watchdog force-closes that same box if it is still open after 5s, so a regression fails instead of
    hanging. Both timers are owned here and stopped by ``stop()`` (and as soon as the box finishes), so
    nothing outlives the test and touches a dialog opened by a later one.
    """

    def __init__(self, dismissal: str) -> None:
        from PySide6.QtCore import QTimer

        self.dismissal = dismissal
        self.done: list[str] = []
        self._box: QMessageBox | None = None
        self._poll = QTimer()
        self._poll.setInterval(10)
        self._poll.timeout.connect(self._dismiss)
        self._watchdog = QTimer()
        self._watchdog.setSingleShot(True)
        self._watchdog.setInterval(5000)
        self._watchdog.timeout.connect(self._force_close)

    def start(self) -> None:
        self._poll.start()
        self._watchdog.start()

    def stop(self) -> None:
        self._poll.stop()
        self._watchdog.stop()

    def _dismiss(self) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        box = QApplication.activeModalWidget()
        if not isinstance(box, QMessageBox) or not box.isVisible():
            return
        self._poll.stop()
        self._box = box
        box.finished.connect(self._watchdog.stop)
        if self.dismissal == "escape":
            QTest.keyClick(box, Qt.Key.Key_Escape)
        else:
            box.close()
        self.done.append(self.dismissal)

    def _force_close(self) -> None:
        self._poll.stop()
        box = self._box if self._box is not None else QApplication.activeModalWidget()
        if isinstance(box, QMessageBox) and box.isVisible():
            box.done(0)


@pytest.fixture
def dismiss_shown_box(controller: UIController) -> Iterator[Callable[[str], _ShownBoxDismisser]]:
    dismissers: list[_ShownBoxDismisser] = []

    def start(dismissal: str) -> _ShownBoxDismisser:
        dismisser = _ShownBoxDismisser(dismissal)
        dismissers.append(dismisser)
        dismisser.start()
        return dismisser

    yield start
    for dismisser in dismissers:
        dismisser.stop()


@pytest.mark.parametrize("dismissal", ["escape", "close"])
def test_show_choice_returns_none_when_a_shown_dialog_is_dismissed(
    controller: UIController, dismiss_shown_box: Callable[[str], _ShownBoxDismisser], dismissal: str
) -> None:
    """Regression (#629 review): with a single RejectRole button Qt makes that button the escape button,
    so Esc or the title-bar close clicked "Discard" and deleted the recovery copy. Dismissing must not
    pick either choice."""
    dismisser = dismiss_shown_box(dismissal)

    assert controller.show_choice("Restore Project", "Message", "Restore", "Discard") is None
    assert dismisser.done == [dismissal]
    assert not dismisser._watchdog.isActive()
