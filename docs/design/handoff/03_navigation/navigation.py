"""Step 2B picks: 2j PTabWidget (underline) · 2l PRailTabs (vertical, Settings only) · 2m PanelShell (classic footer)
· Dialogs by purpose: PDialog (2p standard, small dialogs) · PNavDialog (2q sidebar, Settings) · PStepDialog (2r stepper, wizards).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QListWidget,
                               QScrollArea, QStackedWidget, QTabWidget, QToolButton, QVBoxLayout, QWidget)

from ..common.dirty_footer import DirtyFooter  # existing
from ..common.p_button import PButton          # existing


def _repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)


# ---------- Tabs ----------
class PTabWidget(QTabWidget):
    """2j — underline tabs. Use everywhere except Settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("ptabs", True)  # noqa: FBT003
        self.setDocumentMode(True)
        self.setUsesScrollButtons(True)
        self.tabBar().setDrawBase(False)
        self.tabBar().setExpanding(False)


class PRailTabs(QWidget):
    """2l — vertical rail (QListWidget + QStackedWidget). Settings dialog only."""

    currentChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.rail = QListWidget()
        self.rail.setProperty("rail", True)  # noqa: FBT003
        self.rail.setFixedWidth(120)
        self.stack = QStackedWidget()
        lay.addWidget(self.rail)
        lay.addWidget(self.stack, 1)
        self.rail.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.rail.currentRowChanged.connect(self.currentChanged)

    def add_tab(self, w: QWidget, label: str):
        self.stack.addWidget(w)
        self.rail.addItem(label)
        if self.rail.count() == 1:
            self.rail.setCurrentRow(0)


# ---------- Panel shell ----------
class PanelShell(QWidget):
    """2m — header (title + close), scroll body, always-visible DirtyFooter (disabled when clean)."""

    close_requested = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.header = QFrame()
        self.header.setProperty("shellHeader", True)  # noqa: FBT003
        self.header.setProperty("scrolled", False)  # noqa: FBT003
        h = QHBoxLayout(self.header)
        h.setContentsMargins(10, 8, 10, 8)
        t = QLabel(title)
        t.setProperty("shellTitle", True)  # noqa: FBT003
        close = QToolButton()
        close.setText("×")
        close.setProperty("iconButton", True)  # noqa: FBT003
        close.clicked.connect(self.close_requested)
        h.addWidget(t)
        h.addStretch()
        h.addWidget(close)

        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(10, 8, 10, 8)
        self.body_layout.setSpacing(8)
        self.body_layout.addStretch()
        self.scroll.setWidget(body)
        self.scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self.footer = DirtyFooter()
        self.footer.setProperty("shellFooter", True)  # noqa: FBT003

        lay.addWidget(self.header)
        lay.addWidget(self.scroll, 1)
        lay.addWidget(self.footer)

    def add_section(self, w: QWidget):
        self.body_layout.insertWidget(self.body_layout.count() - 1, w)

    def _on_scroll(self, v: int):
        on = v > 0
        if self.header.property("scrolled") != on:
            self.header.setProperty("scrolled", on)
            _repolish(self.header)


# ---------- Dialogs ----------
class PDialog(QDialog):
    """2p — standard: title 15/600, body margins 14, QDialogButtonBox (platform order). Small dialogs, confirms."""

    def __init__(self, title: str, primary: str = "OK", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setProperty("pdialog", True)  # noqa: FBT003
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._title = QLabel(title)
        self._title.setProperty("dialogTitle", True)  # noqa: FBT003
        self._title.setContentsMargins(14, 12, 14, 10)
        root.addWidget(self._title)
        self.header_extra = QVBoxLayout()  # stepper slot
        self.header_extra.setContentsMargins(14, 0, 14, 10)
        root.addLayout(self.header_extra)
        div = QFrame()
        div.setProperty("hairline", True)  # noqa: FBT003
        div.setFixedHeight(1)
        root.addWidget(div)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(14, 12, 14, 12)
        self.content_layout.setSpacing(8)
        root.addWidget(self.content, 1)
        foot = QFrame()
        foot.setProperty("dialogFooter", True)  # noqa: FBT003
        self.footer_layout = QHBoxLayout(foot)
        self.footer_layout.setContentsMargins(14, 10, 14, 10)
        self.buttons = QDialogButtonBox()
        self.cancel_btn = PButton("Cancel", role="secondary")
        self.primary_btn = PButton(primary, role="primary")
        self.buttons.addButton(self.cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        self.buttons.addButton(self.primary_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.footer_layout.addStretch()
        self.footer_layout.addWidget(self.buttons)
        root.addWidget(foot)

    def set_valid(self, ok: bool):
        self.primary_btn.setEnabled(ok)


class PNavDialog(PDialog):
    """2q — sidebar nav (uses PRailTabs styling). Settings / large multi-section dialogs."""

    def __init__(self, title: str, primary: str = "Save", parent=None):
        super().__init__(title, primary, parent)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = PRailTabs()
        self.pages.rail.setProperty("dialogNav", True)  # noqa: FBT003
        self.content_layout.addWidget(self.pages)

    def add_page(self, w: QWidget, label: str):
        self.pages.add_tab(w, label)


class PStepDialog(PDialog):
    """2r — stepper header + Back / Cancel / Next|Finish. Wizards (New chart, Import)."""

    def __init__(self, title: str, steps: list[str], parent=None):
        super().__init__(title, "Next", parent)
        self._steps, self._i = steps, 0
        self._dots: list[QLabel] = []
        row = QHBoxLayout()
        row.setSpacing(6)
        for n, s in enumerate(steps):
            d = QLabel(str(n + 1))
            d.setProperty("stepDot", "todo")
            d.setFixedSize(16, 16)
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl = QLabel(s)
            lbl.setProperty("stepLabel", True)  # noqa: FBT003
            row.addWidget(d)
            row.addWidget(lbl)
            self._dots.append(d)
        row.addStretch()
        self.header_extra.addLayout(row)
        self.stack = QStackedWidget()
        self.content_layout.addWidget(self.stack)
        self.back_btn = PButton("Back", role="secondary", on_click=self.back)
        self.footer_layout.insertWidget(0, self.back_btn)
        self.buttons.accepted.disconnect()
        self.primary_btn.clicked.connect(self.next)
        self._sync()

    def add_step(self, w: QWidget):
        self.stack.addWidget(w)

    def back(self):
        self._i = max(0, self._i - 1)
        self._sync()

    def next(self):
        if self._i == len(self._steps) - 1:
            self.accept()
            return
        self._i += 1
        self._sync()

    def _sync(self):
        self.stack.setCurrentIndex(self._i)
        self.back_btn.setVisible(self._i > 0)
        self.primary_btn.setText("Finish" if self._i == len(self._steps) - 1 else "Next")
        for n, d in enumerate(self._dots):
            d.setProperty("stepDot", "done" if n < self._i else "current" if n == self._i else "todo")
            d.setText("✓" if n < self._i else str(n + 1))
            _repolish(d)


def nav_qss(t: dict) -> str:
    return f"""
QTabWidget[ptabs="true"]::pane {{ border:none; border-top:1px solid {t['border_subtle']}; }}
QTabWidget[ptabs="true"] QTabBar::tab {{ background:transparent; color:{t['text_muted']}; padding:0 10px;
  min-height:{t['control_h'] + 2}px; border:1px solid transparent; border-bottom:2px solid transparent; }}
QTabWidget[ptabs="true"] QTabBar::tab:selected {{ color:{t['text_primary']}; font-weight:600; border-bottom-color:{t['accent']}; }}
QTabWidget[ptabs="true"] QTabBar::tab:hover:!selected {{ color:{t['text_primary']}; border-bottom-color:{t['border_control']}; }}
QTabWidget[ptabs="true"] QTabBar::tab:focus {{ border-color:{t['focus']}; }}
QTabWidget[ptabs="true"] QTabBar::tab:disabled {{ color:{t['text_disabled']}; }}

QListWidget[rail="true"] {{ background:transparent; border:none; border-right:1px solid {t['border_subtle']}; outline:0; }}
QListWidget[rail="true"][dialogNav="true"] {{ background:{t['bg_inset']}; padding:8px 6px; }}
QListWidget[rail="true"]::item {{ min-height:{t['control_h']}px; padding:0 8px; border-radius:4px; color:{t['text_secondary']}; }}
QListWidget[rail="true"]::item:hover {{ background:{t['bg_inset']}; }}
QListWidget[rail="true"]::item:selected {{ background:{t['accent_sel_bg']}; color:{t['accent_sel_text']}; font-weight:600; }}

QFrame[shellHeader="true"] {{ background:{t['bg_surface']}; border:none; border-bottom:1px solid transparent; }}
QFrame[shellHeader="true"][scrolled="true"] {{ border-bottom-color:{t['border_panel']}; }}
QLabel[shellTitle="true"] {{ font-size:13px; font-weight:600; color:{t['text_primary']}; }}
QWidget[shellFooter="true"] {{ background:{t['bg_surface']}; border-top:1px solid {t['border_panel']}; }}

QDialog[pdialog="true"] {{ background:{t['bg_surface']}; }}
QLabel[dialogTitle="true"] {{ font-size:15px; font-weight:600; color:{t['text_primary']}; }}
QFrame[dialogFooter="true"] {{ border-top:1px solid {t['border_subtle']}; }}
QLabel[stepDot] {{ border-radius:8px; font-size:10px; font-weight:700; border:1px solid {t['border_control']}; color:{t['text_muted']}; }}
QLabel[stepDot="current"] {{ background:{t['accent_sel_bg']}; color:{t['accent_sel_text']}; border-color:{t['accent']}; }}
QLabel[stepDot="done"] {{ background:{t['accent']}; color:{t['on_accent']}; border-color:{t['accent']}; }}
QLabel[stepLabel="true"] {{ font-size:11px; color:{t['text_muted']}; }}
"""
