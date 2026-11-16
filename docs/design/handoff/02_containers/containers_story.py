"""Storybook story: state matrix for Card / CollapsibleSection / SubGroup."""
from PySide6.QtWidgets import QDoubleSpinBox, QGridLayout, QLabel, QWidget

from .containers import Card, CollapsibleSection, SubGroup


def _field(v: float) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setValue(v)
    return s


class ContainersStory(QWidget):
    title = "Containers"

    def __init__(self, parent=None):
        super().__init__(parent)
        g = QGridLayout(self)
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(12)

        for col, (name, cfg) in enumerate([("rest", {}), ("selected", {"sel": True}), ("disabled", {"dis": True})]):
            g.addWidget(QLabel(f"Card · {name}"), 0, col)
            c = Card("Range", "Auto")
            c.body.addWidget(_field(0))
            c.body.addWidget(_field(100))
            c.set_selected(cfg.get("sel", False))
            c.setEnabled(not cfg.get("dis", False))
            g.addWidget(c, 1, col)

        for col, (name, exp, mod) in enumerate([("expanded", True, False), ("collapsed", False, False),
                                                 ("modified · collapsed", False, True)]):
            g.addWidget(QLabel(f"Section · {name}"), 2, col)
            s = CollapsibleSection("Line", expanded=exp)
            s.add_widget(_field(1.5))
            s.set_modified(mod)
            g.addWidget(s, 3, col)

        for col, (name, dis) in enumerate([("enabled", False), ("disabled", True)]):
            g.addWidget(QLabel(f"SubGroup · {name}"), 4, col)
            sg = SubGroup("Markers")
            sg.add_widget(_field(6))
            sg.setEnabled(not dis)
            g.addWidget(sg, 5, col)
        g.setRowStretch(6, 1)
