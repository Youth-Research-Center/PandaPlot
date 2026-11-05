"""Editable DPI picker for chart snapshots: a preset, a typed value, or the chart's own DPI."""

from PySide6.QtWidgets import QComboBox, QWidget

from pandaplot.gui.components.common.drop_down_combo_box import DropDownComboBox
from pandaplot.models.project.items.image import MAX_RENDER_DPI, MIN_RENDER_DPI

CHART_DEFAULT_LABEL = "Chart default"
_PRESET_DPIS = (72, 100, 150, 300, 600)


def _clamp(dpi: int) -> int:
    return min(max(dpi, MIN_RENDER_DPI), MAX_RENDER_DPI)


class SnapshotDpiComboBox(DropDownComboBox):
    """Editable combo offering "Chart default" (no override) and common DPI
    presets; any whole number can be typed and is clamped to the supported
    range. Read the choice with `value()`: None means "use the chart's own DPI".
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.addItem(CHART_DEFAULT_LABEL, None)
        for dpi in _PRESET_DPIS:
            self.addItem(str(dpi), dpi)
        self.setAccessibleName("Snapshot DPI")
        self.setAccessibleDescription(
            f"Resolution of the chart snapshot, {MIN_RENDER_DPI} to {MAX_RENDER_DPI} dpi, or the chart's own DPI")
        self.lineEdit().editingFinished.connect(self._normalize_text)

    def value(self) -> int | None:
        """The chosen DPI, clamped to the supported range, or None for the chart's own DPI
        (also for text that is not a whole number)."""
        try:
            return _clamp(int(self.currentText().strip()))
        except ValueError:
            return None

    def set_value(self, dpi: int | None) -> None:
        """Show `dpi` (clamped), or "Chart default" for None."""
        if dpi is None:
            self.setCurrentIndex(0)
            return
        text = str(_clamp(dpi))
        index = self.findText(text)
        if index >= 0:
            self.setCurrentIndex(index)
        else:
            self.setEditText(text)

    def _normalize_text(self) -> None:
        """Rewrite what was typed as the value it will be used as."""
        dpi = self.value()
        self.setEditText(CHART_DEFAULT_LABEL if dpi is None else str(dpi))
