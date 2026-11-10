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


@pytest.mark.parametrize(("clicked", "accepted"), [("Restore", True), ("Discard", False), (None, False)])
def test_show_choice_returns_true_only_for_the_accept_button(
    controller: UIController, monkeypatch: pytest.MonkeyPatch, clicked: str | None, accepted: object
) -> None:
    _click_on_exec(monkeypatch, clicked)

    assert controller.show_choice("Restore Project", "Message", "Restore", "Discard") is accepted
