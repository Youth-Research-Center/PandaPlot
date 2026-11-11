"""Tests for UIController.show_save_as_discard_cancel and show_choice (#629).

QMessageBox.exec is replaced by a function that clicks the named button, so no modal loop runs.
"""
import sys

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


def _dismiss_shown_box(dismissal: str) -> list[str]:
    """Dismiss the next shown QMessageBox by a real Esc key press or a real close, from a timer.

    A second timer force-closes any box still open after 5s, so a regression fails instead of hanging.
    """
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest

    done: list[str] = []

    def dismiss() -> None:
        box = QApplication.activeModalWidget()
        if not isinstance(box, QMessageBox) or not box.isVisible():
            QTimer.singleShot(10, dismiss)
            return
        if dismissal == "escape":
            QTest.keyClick(box, Qt.Key.Key_Escape)
        else:
            box.close()
        done.append(dismissal)

    def force_close() -> None:
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                widget.done(0)

    QTimer.singleShot(0, dismiss)
    QTimer.singleShot(5000, force_close)
    return done


@pytest.mark.parametrize("dismissal", ["escape", "close"])
def test_show_choice_returns_none_when_a_shown_dialog_is_dismissed(controller: UIController, dismissal: str) -> None:
    """Regression (#629 review): with a single RejectRole button Qt makes that button the escape button,
    so Esc or the title-bar close clicked "Discard" and deleted the recovery copy. Dismissing must not
    pick either choice."""
    done = _dismiss_shown_box(dismissal)

    assert controller.show_choice("Restore Project", "Message", "Restore", "Discard") is None
    assert done == [dismissal]
