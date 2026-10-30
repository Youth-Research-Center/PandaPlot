"""Small dialog for choosing the DPI a chart snapshot is re-rendered at."""

from typing import override

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.common.snapshot_dpi_combo_box import SnapshotDpiComboBox
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.state.app_context import AppContext


class SnapshotDpiDialog(PDialog):
    """Asks for a snapshot's DPI, starting from its current one."""

    def __init__(self, app_context: AppContext, current_dpi: int | None = None, parent: QWidget | None = None):
        super().__init__(app_context=app_context, parent=parent)
        self._initial_dpi = current_dpi
        self._initialize()

    @override
    def _init_ui(self):
        self.setWindowTitle("Snapshot DPI")
        layout = QVBoxLayout(self)
        label = QLabel("Re-render this snapshot at:")
        self.dpi_combo = SnapshotDpiComboBox()
        self.dpi_combo.set_value(self._initial_dpi)
        label.setBuddy(self.dpi_combo)
        layout.addWidget(label)
        layout.addWidget(self.dpi_combo)

        button_row = QHBoxLayout()
        self.cancel_button = PButton("Cancel", role="secondary", on_click=self.reject)
        self.ok_button = PButton("Re-render", role="primary", on_click=self.accept)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.ok_button)
        layout.addLayout(button_row)

    @override
    def _apply_theme(self):
        pass

    def get_dpi(self) -> int | None:
        """Return the chosen DPI, or None to follow the chart's own DPI."""
        return self.dpi_combo.value()
