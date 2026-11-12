"""Step 2A picks: 2b Card (inset fill) · 2d CollapsibleSection (caps + left chevron) · 2h SubGroup (sub-label + hairline).

Tokens come from 01_tokens/design_tokens.py. All styling is QSS-driven (see CONTAINERS_QSS);
widgets only set dynamic properties and call _repolish().
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy, QToolButton,
                               QVBoxLayout, QWidget)


def _repolish(w: QWidget):
    w.style().unpolish(w)
    w.style().polish(w)


class Card(QFrame):
    """2b — bg_inset tile, transparent 1px border reserved for selected/focus (no layout shift)."""

    def __init__(self, title: str | None = None, meta: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("card", True)  # noqa: FBT003
        self.setProperty("selected", False)  # noqa: FBT003
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)
        self.body = lay
        if title:
            row = QHBoxLayout()
            self.title_label = QLabel(title)
            self.title_label.setProperty("cardTitle", True)  # noqa: FBT003
            row.addWidget(self.title_label)
            row.addStretch()
            if meta:
                m = QLabel(meta)
                m.setProperty("cardMeta", True)  # noqa: FBT003
                row.addWidget(m)
            lay.addLayout(row)

    def set_selected(self, on: bool):
        self.setProperty("selected", on)
        _repolish(self)
        if hasattr(self, "title_label"):
            _repolish(self.title_label)

    def set_tokens(self, tokens: dict):
        _repolish(self)


class CollapsibleSection(QWidget):
    """2d — uppercase 10.5px label, left chevron, 'Reset' on hover or when modified, accent dot when modified."""

    toggled = Signal(bool)
    reset_requested = Signal()

    def __init__(self, title: str, expanded: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self._modified = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        hdr = QWidget()
        h = QHBoxLayout(hdr)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        self.button = QToolButton()
        self.button.setProperty("section", True)  # noqa: FBT003
        self.button.setText(title.upper())
        self.button.setCheckable(True)
        self.button.setChecked(expanded)
        self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.button.toggled.connect(self._on_toggled)
        self.dot = QLabel()
        self.dot.setProperty("modifiedDot", True)  # noqa: FBT003
        self.dot.setFixedSize(6, 6)
        self.dot.hide()
        self.reset = QToolButton()
        self.reset.setProperty("sectionAction", True)  # noqa: FBT003
        self.reset.setText("Reset")
        self.reset.hide()
        self.reset.clicked.connect(self.reset_requested)
        h.addWidget(self.button, 1)
        h.addWidget(self.dot)
        h.addWidget(self.reset)
        lay.addWidget(hdr)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(4, 0, 0, 0)
        self.content_layout.setSpacing(6)
        lay.addWidget(self.content)
        self._sync_arrow(expanded)
        self.content.setVisible(expanded)
        hdr.installEventFilter(self)
        self._hdr = hdr

    def eventFilter(self, obj, ev):  # show Reset on hover
        if obj is self._hdr and ev.type() in (ev.Type.Enter, ev.Type.Leave):
            self.reset.setVisible(self._modified or ev.type() == ev.Type.Enter)
        return False

    def _sync_arrow(self, open_: bool):
        self.button.setArrowType(Qt.ArrowType.DownArrow if open_ else Qt.ArrowType.RightArrow)

    def _on_toggled(self, on: bool):
        self._sync_arrow(on)
        self.content.setVisible(on)
        self.toggled.emit(on)

    def set_modified(self, on: bool):
        self._modified = on
        self.dot.setVisible(on)
        self.reset.setVisible(on)

    def add_widget(self, w: QWidget):
        self.content_layout.addWidget(w)

    def set_tokens(self, tokens: dict):
        for w in (self.button, self.dot, self.reset):
            _repolish(w)


class SubGroup(QWidget):
    """2h — sentence-case label + hairline; no indent, label column stays aligned with parent."""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.label = QLabel(title)
        self.label.setProperty("subgroup", True)  # noqa: FBT003
        rule = QFrame()
        rule.setProperty("hairline", True)  # noqa: FBT003
        rule.setFixedHeight(1)
        row.addWidget(self.label)
        row.addWidget(rule, 1)
        lay.addLayout(row)
        self.content_layout = lay

    def add_widget(self, w: QWidget):
        self.content_layout.addWidget(w)

    def set_tokens(self, tokens: dict):
        _repolish(self.label)


def containers_qss(t: dict) -> str:
    hover_bg = _mix(t["bg_inset"], t["border_panel"], 0.45)
    return f"""
QFrame[card="true"] {{ background:{t['bg_inset']}; border:1px solid {t['bg_inset']}; border-radius:6px; }}
QFrame[card="true"]:hover {{ background:{hover_bg}; border-color:{hover_bg}; }}
QFrame[card="true"][selected="true"] {{ background:{t['accent_sel_bg']}; border-color:{t['accent']}; }}
QFrame[card="true"]:focus {{ border-color:{t['focus']}; }}
QFrame[card="true"]:disabled QLabel {{ color:{t['text_disabled']}; }}
QLabel[cardTitle="true"] {{ font-weight:600; color:{t['text_primary']}; }}
QFrame[card="true"][selected="true"] QLabel[cardTitle="true"] {{ color:{t['accent_sel_text']}; }}
QLabel[cardMeta="true"] {{ font-size:11px; color:{t['text_muted']}; }}

QToolButton[section="true"] {{ background:transparent; border:1px solid transparent; border-radius:4px;
  padding:2px 4px; color:{t['text_muted']}; font-size:10.5px; font-weight:700; letter-spacing:1px; text-align:left; }}
QToolButton[section="true"]:hover {{ color:{t['text_primary']}; }}
QToolButton[section="true"]:focus {{ border-color:{t['focus']}; }}
QToolButton[section="true"]:disabled {{ color:{t['text_disabled']}; }}
QToolButton[sectionAction="true"] {{ background:transparent; border:none; color:{t['accent_sel_text']}; font-size:11px; font-weight:600; }}
QLabel[modifiedDot="true"] {{ background:{t['accent']}; border-radius:3px; }}

QLabel[subgroup="true"] {{ color:{t['text_secondary']}; font-size:11.5px; font-weight:600; }}
QLabel[subgroup="true"]:disabled {{ color:{t['text_disabled']}; }}
QFrame[hairline="true"] {{ background:{t['border_subtle']}; border:none; }}
"""


def _mix(a: str, b: str, t: float) -> str:
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(pa, pb))
