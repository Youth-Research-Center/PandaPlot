"""Step 4 picks — each form for its job:
4a1 CheckList (plain rows) · series visibility, legend, layers (short, always visible)
4b2 ChipSelect (single line, "+N" overflow) · filters in dense panels
4c1 DualList (arrow buttons) · ordered / long lists in dialogs & wizards only (≥ 280px)
"""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListView, QToolButton,
                               QVBoxLayout, QWidget)

from ..common.p_button import PButton

ROLE_VALUE = Qt.ItemDataRole.UserRole + 1
ROLE_SWATCH = Qt.ItemDataRole.UserRole + 2
ROLE_META = Qt.ItemDataRole.UserRole + 3


def make_model(items) -> QStandardItemModel:
    """items: iterable of (label, value, swatch_hex | None, meta | None, checked)"""
    m = QStandardItemModel()
    for label, value, swatch, meta, checked in items:
        it = QStandardItem(label)
        it.setCheckable(True)
        it.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        it.setData(value, ROLE_VALUE)
        it.setData(swatch, ROLE_SWATCH)
        it.setData(meta, ROLE_META)
        it.setEditable(False)
        m.appendRow(it)
    return m


class CheckList(QWidget):
    """4a1 — tri-state 'All' header + checkable rows. Only the checkbox shows state (no row tint)."""

    selectionChanged = Signal(list)

    def __init__(self, model: QStandardItemModel, all_label="All", parent=None):
        super().__init__(parent)
        self.model = model
        self.setProperty("checklist", True)  # noqa: FBT003
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        hdr = QFrame()
        hdr.setProperty("checklistHeader", True)  # noqa: FBT003
        h = QHBoxLayout(hdr)
        h.setContentsMargins(8, 0, 8, 0)
        self.all = QCheckBox(all_label)
        self.all.setTristate(True)
        self.count = QLabel()
        self.count.setProperty("meta", True)  # noqa: FBT003
        h.addWidget(self.all, 1)
        h.addWidget(self.count)
        self.view = QListView()
        self.view.setModel(model)
        self.view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)  # Shift+click ranges
        self.view.setUniformItemSizes(True)
        lay.addWidget(hdr)
        lay.addWidget(self.view)
        self.all.clicked.connect(self._toggle_all)
        model.itemChanged.connect(self._sync)
        self._sync()

    def checked_values(self) -> list:
        return [self.model.item(r).data(ROLE_VALUE) for r in range(self.model.rowCount())
                if self.model.item(r).checkState() == Qt.CheckState.Checked]

    def _toggle_all(self):
        on = self.all.checkState() != Qt.CheckState.Unchecked
        self.model.blockSignals(True)
        for r in range(self.model.rowCount()):
            self.model.item(r).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        self.model.blockSignals(False)
        self.view.viewport().update()
        self._sync()

    def _sync(self, *_):
        n, total = len(self.checked_values()), self.model.rowCount()
        self.all.blockSignals(True)
        self.all.setCheckState(Qt.CheckState.Checked if n == total and total else
                               Qt.CheckState.Unchecked if n == 0 else Qt.CheckState.PartiallyChecked)
        self.all.blockSignals(False)
        self.count.setText(f"{n} of {total}")
        self.selectionChanged.emit(self.checked_values())


class ChipSelect(QWidget):
    """4b2 — single-line field (control_h) with chips, '+N' overflow, chevron. Opens a CheckList popup."""

    selectionChanged = Signal(list)

    def __init__(self, model: QStandardItemModel, placeholder="Select…", parent=None):
        super().__init__(parent)
        self.model = model
        self.setProperty("chipField", True)  # noqa: FBT003
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(4, 2, 4, 2)
        self._lay.setSpacing(4)
        self._placeholder = placeholder
        self._chev = QToolButton()
        self._chev.setArrowType(Qt.ArrowType.DownArrow)
        self._chev.setProperty("iconButton", True)  # noqa: FBT003
        self._chev.clicked.connect(self.open_popup)
        self.popup = QFrame(self, Qt.WindowType.Popup)
        self.popup.setProperty("popup", True)  # noqa: FBT003
        pl = QVBoxLayout(self.popup)
        pl.setContentsMargins(3, 3, 3, 3)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter…")
        self.list = CheckList(model)
        pl.addWidget(self.filter)
        pl.addWidget(self.list)
        self.filter.textChanged.connect(self._filter)
        self.list.selectionChanged.connect(self._rebuild)
        self._rebuild()

    def mousePressEvent(self, e):
        self.open_popup()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Down, Qt.Key.Key_Space):
            self.open_popup()
        elif e.key() == Qt.Key.Key_Backspace:
            vals = self.list.checked_values()
            if vals:
                self._set_checked(vals[-1], False)
        else:
            super().keyPressEvent(e)

    def open_popup(self):
        self.popup.setFixedWidth(max(self.width(), 200))
        self.popup.move(self.mapToGlobal(self.rect().bottomLeft()))
        self.popup.show()
        self.filter.setFocus()

    def _filter(self, text: str):
        for r in range(self.model.rowCount()):
            self.list.view.setRowHidden(r, text.lower() not in self.model.item(r).text().lower())

    def _set_checked(self, value, on: bool):
        for r in range(self.model.rowCount()):
            it = self.model.item(r)
            if it.data(ROLE_VALUE) == value:
                it.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def _rebuild(self, *_):
        while self._lay.count():
            w = self._lay.takeAt(0).widget()
            if w and w is not self._chev:
                w.deleteLater()
        checked = [self.model.item(r) for r in range(self.model.rowCount())
                   if self.model.item(r).checkState() == Qt.CheckState.Checked]
        if not checked:
            ph = QLabel(self._placeholder)
            ph.setProperty("placeholder", True)  # noqa: FBT003
            self._lay.addWidget(ph)
        avail = max(0, self.width() - 40)
        used = 0
        shown = 0
        for it in checked:
            chip = _Chip(it.text(), it.data(ROLE_SWATCH), lambda v=it.data(ROLE_VALUE): self._set_checked(v, False))
            w = chip.sizeHint().width() + 4
            if shown and used + w > avail:
                chip.deleteLater()
                break
            self._lay.addWidget(chip)
            used += w
            shown += 1
        if shown < len(checked):
            more = QLabel(f"+{len(checked) - shown}")
            more.setProperty("meta", True)  # noqa: FBT003
            self._lay.addWidget(more)
        self._lay.addStretch()
        self._lay.addWidget(self._chev)
        self.selectionChanged.emit([it.data(ROLE_VALUE) for it in checked])

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._rebuild()

    def sizeHint(self):
        return QSize(200, 26)


class _Chip(QFrame):
    def __init__(self, text, swatch, on_remove):
        super().__init__()
        self.setProperty("chip", True)  # noqa: FBT003
        lay = QHBoxLayout(self)
        lay.setContentsMargins(7, 0, 2, 0)
        lay.setSpacing(5)
        if swatch:
            sw = QFrame()
            sw.setFixedSize(8, 3)
            sw.setStyleSheet(f"background:{swatch}; border-radius:1px;")
            lay.addWidget(sw)
        lay.addWidget(QLabel(text))
        x = QToolButton()
        x.setText("×")
        x.setProperty("chipRemove", True)  # noqa: FBT003
        x.clicked.connect(on_remove)
        lay.addWidget(x)


class DualList(QWidget):
    """4c1 — Available | › ‹ » | Selected (ordered, drag to reorder). Dialogs / wizards only."""

    changed = Signal(list)

    def __init__(self, available: list[tuple[str, object, str]], selected=(), right_title="SELECTED", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.left, self.lm = self._pane("AVAILABLE")
        self.right, self.rm = self._pane(right_title, reorder=True)
        mid = QVBoxLayout()
        mid.addStretch()
        self.b_add = PButton("›", icon=True, on_click=self.add)
        self.b_rem = PButton("‹", icon=True, on_click=self.remove)
        self.b_all = PButton("»", icon=True, on_click=self.add_all)
        for b in (self.b_add, self.b_rem, self.b_all):
            mid.addWidget(b)
        mid.addStretch()
        lay.addWidget(self.left[0], 1)
        lay.addLayout(mid)
        lay.addWidget(self.right[0], 1)
        sel_vals = {v for _, v, _ in selected}
        for row in available:
            (self.rm if row[1] in sel_vals else self.lm).appendRow(self._item(*row))
        for v in (self.left[1], self.right[1]):
            v.selectionModel().selectionChanged.connect(self._sync)
        self.left[1].doubleClicked.connect(lambda _: self.add())
        self.right[1].doubleClicked.connect(lambda _: self.remove())
        self._sync()

    @staticmethod
    def _item(label, value, meta):
        it = QStandardItem(label)
        it.setData(value, ROLE_VALUE)
        it.setData(meta, ROLE_META)
        it.setEditable(False)
        return it

    def _pane(self, title, reorder=False):
        box = QFrame()
        box.setProperty("dualPane", True)  # noqa: FBT003
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        hdr = QLabel(title)
        hdr.setProperty("dualHeader", True)  # noqa: FBT003
        view = QListView()
        model = QStandardItemModel()
        view.setModel(model)
        view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        if reorder:
            view.setDragDropMode(QListView.DragDropMode.InternalMove)
        v.addWidget(hdr)
        v.addWidget(view)
        return (box, view), model

    def _move(self, src_view, src, dst, rows=None):
        rows = rows if rows is not None else sorted({i.row() for i in src_view.selectedIndexes()}, reverse=True)
        for r in rows:
            dst.appendRow(src.takeRow(r))
        self._sync()
        self.changed.emit(self.selected_values())

    def add(self):
        self._move(self.left[1], self.lm, self.rm)

    def remove(self):
        self._move(self.right[1], self.rm, self.lm)

    def add_all(self):
        self._move(self.left[1], self.lm, self.rm, rows=list(range(self.lm.rowCount() - 1, -1, -1)))

    def selected_values(self) -> list:
        return [self.rm.item(r).data(ROLE_VALUE) for r in range(self.rm.rowCount())]

    def _sync(self, *_):
        self.b_add.setEnabled(bool(self.left[1].selectedIndexes()))
        self.b_rem.setEnabled(bool(self.right[1].selectedIndexes()))
        self.b_all.setEnabled(self.lm.rowCount() > 0)


def multiselect_qss(t: dict) -> str:
    h, r = t["control_h"], t["radius"]["control"]
    return f"""
QWidget[checklist="true"] {{ border:1px solid {t['border_control']}; border-radius:{r}px; }}
QFrame[checklistHeader="true"] {{ background:{t['bg_inset']}; border-bottom:1px solid {t['border_subtle']}; min-height:{h}px; }}
QWidget[checklist="true"] QListView {{ border:none; background:{t['bg_surface']}; outline:0; }}
QWidget[checklist="true"] QListView::item {{ min-height:{h}px; padding:0 {t['pad_x']}px; color:{t['text_primary']}; }}
QWidget[checklist="true"] QListView::item:hover {{ background:{t['bg_inset']}; }}
QWidget[checklist="true"] QListView::item:selected {{ background:transparent; color:{t['text_primary']}; }}  /* 4a1: no row tint */
QCheckBox::indicator, QListView::indicator {{ width:14px; height:14px; border-radius:3px; border:1px solid {t['border_control']}; background:{t['bg_surface']}; }}
QCheckBox::indicator:checked, QListView::indicator:checked {{ background:{t['accent']}; border-color:{t['accent']}; image:url(:/icons/check-white.svg); }}
QCheckBox::indicator:indeterminate {{ background:{t['accent']}; border-color:{t['accent']}; image:url(:/icons/dash-white.svg); }}
QCheckBox::indicator:disabled, QListView::indicator:disabled {{ background:{t['text_disabled']}; border-color:{t['text_disabled']}; }}
QLabel[meta="true"] {{ font-size:11px; color:{t['text_muted']}; }}

QWidget[chipField="true"] {{ min-height:{h - 2}px; max-height:{h - 2}px; border:1px solid {t['border_control']}; border-radius:{r}px; background:{t['bg_surface']}; }}
QFrame[chip="true"] {{ background:{t['accent_sel_bg']}; border-radius:{r}px; min-height:{h - 6}px; max-height:{h - 6}px; }}
QFrame[chip="true"] QLabel {{ color:{t['accent_sel_text']}; font-size:11.5px; }}
QToolButton[chipRemove="true"] {{ border:none; background:transparent; color:{t['accent_sel_text']}; padding:0 2px; }}
QLabel[placeholder="true"] {{ color:{t['text_muted']}; font-style:italic; padding:0 4px; }}
QFrame[popup="true"] {{ background:{t['bg_surface']}; border:1px solid {t['border_panel']}; border-radius:{r}px; }}

QFrame[dualPane="true"] {{ border:1px solid {t['border_control']}; border-radius:{r}px; }}
QLabel[dualHeader="true"] {{ background:{t['bg_inset']}; border-bottom:1px solid {t['border_subtle']}; min-height:22px; padding:0 {t['pad_x']}px;
  color:{t['text_muted']}; font-size:10.5px; font-weight:700; letter-spacing:0.8px; }}
QFrame[dualPane="true"] QListView {{ border:none; outline:0; }}
QFrame[dualPane="true"] QListView::item {{ min-height:{h}px; padding:0 {t['pad_x']}px; }}
QFrame[dualPane="true"] QListView::item:selected {{ background:{t['accent_sel_bg']}; color:{t['accent_sel_text']}; }}
"""
