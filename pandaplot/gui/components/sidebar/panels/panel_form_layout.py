"""Form layout shared by the sidebar panels, so every panel lays out its
label/field rows the same way."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QLayout, QWidget

LABEL_ALIGNMENT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
FORM_HORIZONTAL_SPACING = 8
FORM_VERTICAL_SPACING = 6
COMBO_MINIMUM_CONTENTS_LENGTH = 8


def compact_combo(combo: QComboBox) -> None:
    """Let a combo box shrink below the width of its longest item.

    By default a combo sizes itself to its widest entry, so one long dataset or
    column name (or a long method label) makes the whole panel wider than the
    sidebar and adds a horizontal scroll bar. The text is elided instead.

    Args:
        combo: The combo box to adjust.
    """
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(COMBO_MINIMUM_CONTENTS_LENGTH)


class PanelFormLayout(QFormLayout):
    """``QFormLayout`` with the sidebar's row conventions.

    Labels are left-aligned (macOS right-aligns them by default and the other
    panels' labels are left-aligned), fields grow to the full row width, rows
    never wrap, and spacing is the same in every panel. Combo boxes added as a
    field are made compact (see ``compact_combo``).
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setLabelAlignment(LABEL_ALIGNMENT)
        self.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        self.setVerticalSpacing(FORM_VERTICAL_SPACING)

    def addRow(self, *args: QWidget | QLayout | str) -> None:
        """Add a row as ``QFormLayout.addRow`` does, compacting a combo box field."""
        self._compact_combos(args)
        super().addRow(*args)

    def insertRow(self, row: int, *args: QWidget | QLayout | str) -> None:
        """Insert a row as ``QFormLayout.insertRow`` does, compacting a combo box field."""
        self._compact_combos(args)
        super().insertRow(row, *args)

    def setWidget(self, row: int, role: QFormLayout.ItemRole, widget: QWidget) -> None:
        """Place a widget as ``QFormLayout.setWidget`` does, compacting a combo box."""
        self._compact_combos((widget,))
        super().setWidget(row, role, widget)

    @staticmethod
    def _compact_combos(items: tuple[QWidget | QLayout | str, ...]) -> None:
        for item in items:
            if isinstance(item, QComboBox):
                compact_combo(item)
