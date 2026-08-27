"""Shared footer row for the chart creation wizard: Cancel/Back/Next/Finish
plus an optional "Create empty plot instead" link and a "Step X of Y" label.

Each `ChartWizard` page owns its own `WizardFooter` instance and wires its
signals directly to `self.wizard().back()/next()/accept()/reject()` -- the
footer itself has no reference to the wizard, keeping it independently
testable (see test_wizard_footer.py).
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from pandaplot.gui.components.common.p_button import PButton


class WizardFooter(QWidget):
    backClicked = Signal()
    nextClicked = Signal()
    finishClicked = Signal()
    cancelClicked = Signal()
    emptyRequested = Signal()

    def __init__(self, step_number: int, total_steps: int, *, show_empty_link: bool,
                 show_next: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)

        self.step_label = QLabel(f"Step {step_number} of {total_steps}", self)
        layout.addWidget(self.step_label)

        self.empty_link = None
        if show_empty_link:
            self.empty_link = QPushButton("Create empty plot instead", self)
            self.empty_link.setFlat(True)
            self.empty_link.setCursor(Qt.CursorShape.PointingHandCursor)
            self.empty_link.clicked.connect(self.emptyRequested.emit)
            layout.addWidget(self.empty_link)

        layout.addStretch(1)

        self.back_button = PButton(
            "Back", role="secondary", on_click=self.backClicked.emit, parent=self
        )
        self.back_button.setVisible(step_number > 1)
        layout.addWidget(self.back_button)

        self.cancel_button = PButton(
            "Cancel", role="secondary", on_click=self.cancelClicked.emit, parent=self
        )
        layout.addWidget(self.cancel_button)

        is_last_step = step_number == total_steps
        self.next_button = PButton(
            "Next", role="primary", on_click=self.nextClicked.emit, parent=self
        )
        self.next_button.setVisible(show_next and not is_last_step)
        layout.addWidget(self.next_button)

        self.finish_button = PButton(
            "Create Chart", role="primary", on_click=self.finishClicked.emit, parent=self
        )
        self.finish_button.setVisible(show_next and is_last_step)
        layout.addWidget(self.finish_button)

    def set_back_enabled(self, *, enabled: bool) -> None:
        self.back_button.setEnabled(enabled)

    def set_next_enabled(self, *, enabled: bool) -> None:
        self.next_button.setEnabled(enabled)
        self.finish_button.setEnabled(enabled)

    def set_tokens(self, tokens: dict) -> None:
        accent = tokens.get("accent", "#4A56C6")
        text_hint = tokens.get("text_hint", "#9AA0AB")

        self.step_label.setStyleSheet(f"color: {text_hint}; font-size: 10.5px;")
        if self.empty_link is not None:
            self.empty_link.setStyleSheet(
                f"QPushButton {{ color: {accent}; font-weight: 600; border: none; }}"
            )
