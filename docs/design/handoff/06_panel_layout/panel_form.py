"""Panel content layout — rules approved in Step 6 (side panels 260–360px).

PanelForm replaces ad-hoc QFormLayout/QGridLayout inside side-panel sections.
Rows are added through typed helpers so every panel gets the same rules:

  field(label, w)        label above, control on its own line indented 10px (spacing 3)
  field(None, w)         "bare" field — label dropped because it repeats the section/panel title;
                         no indent. The label text is still set as accessibleName.
  inline(label, w)       label left, control right — toggles and read-only key/value
  pair(label, a, b)      two controls share the indented line (Range min/max)
  help(text)             muted 11px helper under the previous field, aligned with it
  sub(title, action)     2h sub-group label + hairline (+ optional ghost action)
  widget(w)              full-width block (lists, output areas, code editors)

Lists: multi-select (has "Select all") → CheckList (4a1); single-select → SingleList (highlighted row).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListView, QSizePolicy, QVBoxLayout, QWidget)

from .containers import SubGroup

INDENT = 10
LABEL_GAP = 3
ROW_GAP = 8


class PanelForm(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(ROW_GAP)
        self._last_bare = False

    # -- rows ---------------------------------------------------------------
    def field(self, label: str | None, w: QWidget, accessible: str | None = None) -> QWidget:
        row = QWidget()
        v = QVBoxLayout(row)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(LABEL_GAP)
        if label:
            lab = QLabel(label)
            lab.setProperty("fieldLabel", True)  # noqa: FBT003
            lab.setBuddy(w)
            v.addWidget(lab)
            holder = QHBoxLayout()
            holder.setContentsMargins(INDENT, 0, 0, 0)
            holder.addWidget(w)
            v.addLayout(holder)
            w.setAccessibleName(label)
        else:
            v.addWidget(w)
            if accessible:
                w.setAccessibleName(accessible)
        self._last_bare = not label
        self._lay.addWidget(row)
        return row

    def pair(self, label: str, a: QWidget, b: QWidget) -> QWidget:
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        h.addWidget(a, 1)
        h.addWidget(b, 1)
        return self.field(label, box)

    def inline(self, label: str, w: QWidget) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        lab = QLabel(label)
        lab.setProperty("fieldLabel", True)  # noqa: FBT003
        lab.setBuddy(w)
        lab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        h.addWidget(lab)
        h.addWidget(w, 0, Qt.AlignmentFlag.AlignRight)
        w.setAccessibleName(label)
        self._last_bare = True
        self._lay.addWidget(row)
        return row

    def help(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setProperty("fieldHelp", True)  # noqa: FBT003
        lab.setContentsMargins(0 if self._last_bare else INDENT, 0, 0, 0)
        self._lay.addWidget(lab)
        # pull closer to the field above (ROW_GAP 8 → 4)
        self._lay.setSpacing(ROW_GAP)
        lab.setStyleSheet("margin-top:-4px;")
        return lab

    def sub(self, title: str, action: QWidget | None = None) -> SubGroup:
        g = SubGroup(title)
        if action is not None:
            g.layout().itemAt(0).layout().addWidget(action)
        self._lay.addWidget(g)
        self._last_bare = True
        return g

    def widget(self, w: QWidget) -> QWidget:
        self._lay.addWidget(w)
        self._last_bare = True
        return w


class SingleList(QListView):
    """Single-select list — selected row = accent_sel_bg / accent_sel_text, 600. No checkboxes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("singleList", True)  # noqa: FBT003
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setUniformItemSizes(True)


class OutputArea(QFrame):
    """Results / preview area — bg_surface, border_panel, muted placeholder text."""

    def __init__(self, placeholder: str, min_height: int = 100, parent=None):
        super().__init__(parent)
        self.setProperty("outputArea", True)  # noqa: FBT003
        self.setMinimumHeight(min_height)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 7, 8, 7)
        self.placeholder = QLabel(placeholder)
        self.placeholder.setProperty("placeholder", True)  # noqa: FBT003
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        v.addWidget(self.placeholder)


def panel_form_qss(t: dict) -> str:
    h, px, r = t["control_h"], t["pad_x"], t["radius"]["control"]
    return f"""
QLabel[fieldLabel="true"] {{ color:{t['text_secondary']}; }}
QLabel[fieldLabel="true"]:disabled {{ color:{t['text_disabled']}; }}
QLabel[fieldHelp="true"] {{ color:{t['text_muted']}; font-size:11px; }}
QListView[singleList="true"] {{ background:{t['bg_surface']}; border:1px solid {t['border_control']}; border-radius:{r}px; outline:0; }}
QListView[singleList="true"]::item {{ min-height:{h}px; padding:0 {px}px; color:{t['text_primary']}; }}
QListView[singleList="true"]::item:hover {{ background:{t['bg_inset']}; }}
QListView[singleList="true"]::item:selected {{ background:{t['accent_sel_bg']}; color:{t['accent_sel_text']}; font-weight:600; }}
QFrame[outputArea="true"] {{ background:{t['bg_surface']}; border:1px solid {t['border_panel']}; border-radius:{r}px; }}
"""


# ---------------------------------------------------------------------------
# Example — Statistical Tests (Step 6 #16), content unchanged except approved bare labels
# ---------------------------------------------------------------------------
def build_statistical_tests(shell, ValueComboBox, PSpinField, SegmentedControl, CollapsibleSection, Card):
    def section(title):
        s = CollapsibleSection(title)
        card = Card()
        form = PanelForm()
        card.body.addWidget(form)
        s.add_widget(card)
        shell.add_section(s)
        return form

    f = section("Input")
    f.field(None, ValueComboBox([("Time", "Time")]), accessible="Sample column")

    f = section("Method")
    f.field(None, ValueComboBox([("One-sample t-test", "t1")]), accessible="Test")
    f.help("Tests whether a sample mean differs from an expected value. "
           "Assumes normality and independent observations.")

    f = section("Parameters")
    f.field("Significance α", PSpinField(0.05, decimals=3))
    f.field("Expected mean μ₀", PSpinField(0.0, decimals=3))
    f.field("Alternative", SegmentedControl(["Two-sided", "Less", "Greater"]))

    f = section("Results")
    f.widget(OutputArea("Run a test to see results here…"))

    shell.footer.set_actions(secondary="Run", primary="Add to project")
    shell.footer.set_status("Not run")
