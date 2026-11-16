"""Step 3 picks: 3a PButton (solid + outline) · 3d SliderWithSpinbox (track + unit spinbox) · 3g ValueComboBox (outlined + highlighted row).
3i (searchable, grouped) ships as an opt-in variant: ValueComboBox(searchable=True).
Focus: FocusRing — 2px `focus` ring, 1px outside the control; borders never change on focus.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QHBoxLayout, QLineEdit, QPushButton, QSlider,
                               QWidget)


# ---------- Focus ring ----------
class FocusRing(QWidget):
    """Transparent overlay drawn in the target's parent, 1px outside target, only for keyboard focus."""

    def __init__(self, target: QWidget, color: str, radius: int = 4):
        super().__init__(target.parentWidget())
        self._t, self._c, self._r = target, QColor(color), radius
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()
        target.installEventFilter(self)

    def set_color(self, color: str):
        self._c = QColor(color)
        self.update()

    def eventFilter(self, obj: QObject, ev: QEvent):
        if ev.type() == QEvent.Type.FocusIn and ev.reason() in (Qt.FocusReason.TabFocusReason,
                                                                Qt.FocusReason.BacktabFocusReason,
                                                                Qt.FocusReason.ShortcutFocusReason):
            self._place()
            self.show()
            self.raise_()
        elif ev.type() in (QEvent.Type.FocusOut, QEvent.Type.Hide):
            self.hide()
        elif ev.type() in (QEvent.Type.Move, QEvent.Type.Resize) and self.isVisible():
            self._place()
        return False

    def _place(self):
        self.setGeometry(self._t.geometry().adjusted(-3, -3, 3, 3))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(self._c, 2))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), self._r + 2, self._r + 2)


# ---------- PButton ----------
class PButton(QPushButton):
    """3a — roles: primary · secondary · ghost · destructive; icon=True for square icon buttons."""

    ROLES = ("primary", "secondary", "ghost", "destructive")

    def __init__(self, text: str = "", role: str = "secondary", icon: bool = False,
                 on_click=None, enabled: bool = True, parent=None):
        super().__init__(text, parent)
        assert role in self.ROLES
        self.setProperty("role", role)
        self.setProperty("primary", role == "primary")
        self.setProperty("iconButton", icon)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setEnabled(enabled)
        if on_click:
            self.clicked.connect(on_click)
        self._ring = None

    def showEvent(self, e):
        if self._ring is None and self.parentWidget():
            from pandaplot.services.theme.theme_manager import current_tokens  # noqa: PLC0415
            t = current_tokens()
            self._ring = FocusRing(self, t["danger"] if self.property("role") == "destructive" else t["focus"])
        super().showEvent(e)


# ---------- Slider + spinbox ----------
class SliderWithSpinbox(QWidget):
    """3d — styled QSlider (4px track, 14px knob) + 58px spinbox with unit suffix. Mixed = '—'."""

    valueChanged = Signal(float)

    def __init__(self, minimum=0.0, maximum=100.0, step=1.0, decimals=0, unit="", parent=None):
        super().__init__(parent)
        self._min, self._step = minimum, step
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, round((maximum - minimum) / step))
        self.slider.setProperty("pslider", True)  # noqa: FBT003
        self.spin = QDoubleSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setSingleStep(step)
        self.spin.setDecimals(decimals)
        self.spin.setSuffix(f" {unit}" if unit else "")
        self.spin.setSpecialValueText("—")  # shown at minimum when mixed
        self.spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.spin.setFixedWidth(58)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self.slider.valueChanged.connect(lambda i: self.spin.setValue(self._min + i * self._step))
        self.spin.valueChanged.connect(self._from_spin)
        self._mixed = False

    def _from_spin(self, v: float):
        self.set_mixed(False)
        self.slider.blockSignals(True)
        self.slider.setValue(round((v - self._min) / self._step))
        self.slider.blockSignals(False)
        self.valueChanged.emit(v)

    def set_mixed(self, on: bool):
        self._mixed = on
        self.slider.setProperty("mixed", on)
        self.slider.style().unpolish(self.slider)
        self.slider.style().polish(self.slider)

    def value(self) -> float:
        return self.spin.value()

    def setValue(self, v: float):
        self.spin.setValue(v)


# ---------- Dropdown ----------
class ValueComboBox(QComboBox):
    """3g — merges ValueComboBox + DropDownComboBox. Items are (label, value[, icon]). Popup opens below.
    searchable=True → 3i variant: editable line with QCompleter filter, for long lists (columns, fonts)."""

    def __init__(self, items=(), searchable: bool = False, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("pcombo", True)  # noqa: FBT003
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        for it in items:
            label, value, *icon = it
            self.addItem(*(icon[:1] + [label]) if icon else [label], value)
        if placeholder:
            self.setPlaceholderText(placeholder)
        if searchable:
            self.setEditable(True)
            self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            self.completer().setFilterMode(Qt.MatchFlag.MatchContains)
            self.completer().setCompletionMode(self.completer().CompletionMode.PopupCompletion)
            self.lineEdit().setPlaceholderText("Search…")

    def currentValue(self):
        return self.currentData()

    def setCurrentValue(self, value):
        i = self.findData(value)
        self.setCurrentIndex(i)

    def set_mixed(self):
        self.setCurrentIndex(-1)
        self.setPlaceholderText("Mixed")

    def showPopup(self):  # always below the field (the DropDownComboBox macOS fix)
        super().showPopup()
        popup = self.view().window()
        popup.move(self.mapToGlobal(self.rect().bottomLeft()))


def controls_qss(t: dict) -> str:
    h, px, r = t["control_h"], t["pad_x"], t["radius"]["control"]
    mix = _mix
    dis_acc = t["accent_disabled"]
    return f"""
QPushButton {{ min-height:{h - 2}px; padding:0 {t['button_pad_x']}px; border-radius:{r}px;
  background:{t['bg_surface']}; color:{t['text_primary']}; border:1px solid {t['border_control']}; }}
QPushButton:hover {{ background:{t['bg_inset']}; }}
QPushButton:pressed {{ background:{mix(t['bg_inset'], t['border_panel'], .7)}; }}
QPushButton:disabled {{ color:{t['text_disabled']}; border-color:{t['border_subtle']}; background:transparent; }}
QPushButton[role="primary"] {{ background:{t['accent']}; border-color:{t['accent']}; color:{t['on_accent']}; font-weight:600; }}
QPushButton[role="primary"]:hover {{ background:{t['accent_hover']}; border-color:{t['accent_hover']}; }}
QPushButton[role="primary"]:pressed {{ background:{t['accent_pressed']}; border-color:{t['accent_pressed']}; }}
QPushButton[role="primary"]:disabled {{ background:{dis_acc}; border-color:{dis_acc}; color:{t['on_accent']}; }}
QPushButton[role="ghost"] {{ background:transparent; border-color:transparent; color:{t['accent_sel_text']}; font-weight:600; }}
QPushButton[role="ghost"]:hover {{ background:{t['accent_sel_bg']}; }}
QPushButton[role="destructive"] {{ color:{t['danger']}; border-color:{t['danger']}; }}
QPushButton[role="destructive"]:hover {{ background:{mix(t['bg_surface'], t['danger'], .08)}; }}
QPushButton[iconButton="true"] {{ min-width:{h - 2}px; max-width:{h - 2}px; padding:0; color:{t['text_secondary']}; }}

QSlider[pslider="true"]::groove:horizontal {{ height:4px; background:{t['toggle_off']}; border-radius:2px; }}
QSlider[pslider="true"]::sub-page:horizontal {{ background:{t['accent']}; border-radius:2px; }}
QSlider[pslider="true"]::handle:horizontal {{ width:14px; height:14px; margin:-5px 0; border-radius:7px;
  background:{t['knob']}; border:1px solid {t['border_control']}; }}
QSlider[pslider="true"]::handle:horizontal:pressed, QSlider[pslider="true"]::handle:horizontal:hover {{ border:2px solid {t['accent']}; }}
QSlider[pslider="true"]:disabled::sub-page:horizontal {{ background:{t['border_control']}; }}
QSlider[pslider="true"][mixed="true"]::sub-page:horizontal {{ background:transparent; }}
QSlider[pslider="true"][mixed="true"]::handle:horizontal {{ background:transparent; border-color:transparent; }}

QDoubleSpinBox, QSpinBox, QLineEdit, QComboBox {{ min-height:{h - 2}px; padding:0 {px}px; border-radius:{r}px;
  background:{t['bg_surface']}; color:{t['text_primary']}; border:1px solid {t['border_control']}; }}
QComboBox:hover {{ border-color:{t['text_secondary']}; }}
QComboBox:on {{ border-color:{t['focus']}; }}
QDoubleSpinBox:disabled, QSpinBox:disabled, QLineEdit:disabled, QComboBox:disabled {{ color:{t['text_disabled']}; border-color:{t['border_subtle']}; }}
QComboBox::drop-down {{ border:none; width:18px; }}
QComboBox QAbstractItemView {{ background:{t['bg_surface']}; border:1px solid {t['border_panel']}; border-radius:{r}px; padding:3px; outline:0; }}
QComboBox QAbstractItemView::item {{ min-height:{h - 2}px; padding:0 {px}px; border-radius:3px; color:{t['text_primary']}; }}
QComboBox QAbstractItemView::item:hover {{ background:{t['bg_inset']}; }}
QComboBox QAbstractItemView::item:selected {{ background:{t['accent_sel_bg']}; color:{t['accent_sel_text']}; }}
"""


def _mix(a: str, b: str, t: float) -> str:
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(pa, pb))
