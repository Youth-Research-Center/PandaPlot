"""Storybook story: design tokens (swatches + contrast)."""
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from .design_tokens import get_design_tokens


def _lum(h: str) -> float:
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    x, y = _lum(a), _lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


PAIRS = [("text_primary", "bg_surface", 4.5), ("text_muted", "bg_surface", 4.5),
         ("on_accent", "accent", 4.5), ("accent_sel_text", "accent_sel_bg", 4.5),
         ("danger", "bg_surface", 4.5), ("border_control", "bg_surface", 3.0),
         ("focus", "bg_surface", 3.0)]
SWATCHES = ["bg_canvas", "bg_surface", "bg_inset", "border_panel", "border_control", "border_subtle",
            "text_primary", "text_secondary", "text_muted", "text_disabled", "danger",
            "accent", "accent_hover", "accent_pressed", "accent_sel_bg", "accent_sel_text", "focus"]


class TokensStory(QWidget):
    title = "Tokens"

    def __init__(self, theme: str = "light", parent=None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self.set_theme(theme)

    def set_theme(self, theme: str):
        while self._lay.count():
            w = self._lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        t = get_design_tokens(theme)
        grid = QGridLayout()
        for i, key in enumerate(SWATCHES):
            sw = QFrame()
            sw.setFixedSize(40, 24)
            sw.setStyleSheet(f"background:{t[key]}; border:1px solid {t['border_panel']}; border-radius:4px;")
            grid.addWidget(sw, i // 6 * 2, i % 6)
            grid.addWidget(QLabel(f"{key}\n{t[key]}"), i // 6 * 2 + 1, i % 6)
        box = QWidget()
        box.setLayout(grid)
        self._lay.addWidget(box)
        for fg, bg, need in PAIRS:
            r = contrast(t[fg], t[bg])
            self._lay.addWidget(QLabel(f"{fg} / {bg}: {r:.2f}  {'PASS' if r >= need else 'FAIL'} (≥{need})"))
        self._lay.addStretch()
