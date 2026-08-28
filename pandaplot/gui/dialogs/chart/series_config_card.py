"""One series' configuration card for the chart creation wizard's Data step:
dataset picker, per-role column pickers, an optional error-bars toggle, and
a remove button. Collapsible to a one-line summary via `set_collapsed`,
mirroring the accordion pattern used by the Chart Properties panel's Data tab.
"""
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.card import Card
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.models.chart.chart_type_spec import ChartTypeSpec

_ROLE_LABELS = {
    "x": "X column", "y": "Y column", "values": "Values column",
    "u": "U column", "v": "V column", "magnitude": "Color-by column (optional)",
    # Plain "Z column" rather than "Z (color) column": Z drives point color
    # on a Colormap/Heatmap chart but is the third spatial axis on every
    # 3-D one, and one label has to be true of both.
    "z": "Z column",
}
_ROLE_TO_FIELD = {
    "x": "x_column_id", "y": "y_column_id", "values": "y_column_id",
    "u": "u_column_id", "v": "v_column_id", "magnitude": "magnitude_column_id",
    "z": "z_column_id",
}


class SeriesConfigCard(Card):
    removeRequested = Signal()
    configChanged = Signal()
    datasetChanged = Signal(str)

    def __init__(self, role_spec: ChartTypeSpec, parent: Optional[QWidget] = None, index: int = 0):
        super().__init__(parent)
        self._role_spec = role_spec
        self._role_combos: dict[str, QComboBox] = {}
        self.error_bars_check: Optional[QCheckBox] = None
        self.error_asymmetric_check: Optional[QCheckBox] = None
        self.x_error_column_combo: Optional[QComboBox] = None
        self.y_error_column_combo: Optional[QComboBox] = None
        self.x_error_minus_column_combo: Optional[QComboBox] = None
        self.y_error_minus_column_combo: Optional[QComboBox] = None
        self._collapsed = False
        self._tokens: dict = {}
        self._index = index
        self._build_ui()

    def set_index(self, index: int) -> None:
        self._index = index
        if self._collapsed:
            self._refresh_summary()

    def _build_ui(self):
        outer = QVBoxLayout(self)

        # Collapsed summary row -- always built, shown only while collapsed.
        self._summary_row = QWidget()
        summary_layout = QHBoxLayout(self._summary_row)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        self._swatch = QFrame()
        self._swatch.setFixedSize(10, 10)
        summary_layout.addWidget(self._swatch)
        self.summary_label = QLabel()
        summary_layout.addWidget(self.summary_label, 1)
        self._error_status_label = QLabel()
        summary_layout.addWidget(self._error_status_label)
        self._expand_button = PButton(
            "▸", role="secondary", icon=True, on_click=lambda: self.set_collapsed(collapsed=False)
        )
        summary_layout.addWidget(self._expand_button)
        outer.addWidget(self._summary_row)

        # Full form -- shown only while expanded.
        self._form_widget = QWidget()
        grid = QGridLayout(self._form_widget)
        row = 0

        collapse_row = QHBoxLayout()
        collapse_row.addStretch(1)
        self._collapse_button = PButton(
            "▾", role="secondary", icon=True, on_click=lambda: self.set_collapsed(collapsed=True)
        )
        collapse_row.addWidget(self._collapse_button)
        grid.addLayout(collapse_row, row, 0, 1, 2)
        row += 1

        grid.addWidget(QLabel("Dataset:"), row, 0)
        self.dataset_combo = QComboBox()
        self.dataset_combo.currentIndexChanged.connect(self._on_dataset_changed)
        grid.addWidget(self.dataset_combo, row, 1)
        row += 1

        for role in self._role_spec.roles:
            grid.addWidget(QLabel(f"{_ROLE_LABELS[role]}:"), row, 0)
            combo = QComboBox()
            combo.currentIndexChanged.connect(lambda _index=None: self.configChanged.emit())
            self._role_combos[role] = combo
            setattr(self, f"{role}_column_combo", combo)
            grid.addWidget(combo, row, 1)
            row += 1

        if self._role_spec.supports_error_bars:
            self.error_bars_check = QCheckBox("Add error bars")
            self.error_bars_check.toggled.connect(self._on_error_bars_toggled)
            grid.addWidget(self.error_bars_check, row, 0, 1, 2)
            row += 1

            self.error_asymmetric_check = QCheckBox("Asymmetric Error Bars")
            self.error_asymmetric_check.toggled.connect(self._on_error_symmetry_toggled)
            grid.addWidget(self.error_asymmetric_check, row, 0, 1, 2)
            row += 1

            for error_role, label in (
                ("x_error", "X error (+) column"), ("x_error_minus", "X error (-) column"),
                ("y_error", "Y error (+) column"), ("y_error_minus", "Y error (-) column"),
            ):
                error_label = QLabel(f"{label}:")
                combo = QComboBox()
                combo.currentIndexChanged.connect(lambda _index=None: self.configChanged.emit())
                self._role_combos[error_role] = combo
                setattr(self, f"{error_role}_column_combo", combo)
                grid.addWidget(error_label, row, 0)
                grid.addWidget(combo, row, 1)
                setattr(self, f"_{error_role}_label", error_label)
                row += 1

            self._set_error_controls_visible(visible=False)

        self.remove_button = PButton(
            "Remove", role="destructive", on_click=self.removeRequested.emit
        )
        grid.addWidget(self.remove_button, row, 0, 1, 2)

        outer.addWidget(self._form_widget)
        self._update_visibility()

    # -- Collapse/expand --------------------------------------------------

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, *, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._update_visibility()
        if collapsed:
            self._refresh_summary()

    def _update_visibility(self):
        self._summary_row.setVisible(self._collapsed)
        self._form_widget.setVisible(not self._collapsed)

    def _refresh_summary(self):
        names = self.get_display_names()
        dataset_name = self.dataset_combo.currentText() or "—"
        if "values" in names:
            text = f"{dataset_name} — {names['values']}"
        else:
            x_name = names.get("x", "—")
            y_name = names.get("y", "—")
            text = f"{dataset_name} — {x_name} : {y_name}"
        self.summary_label.setText(text)
        palette = self._tokens.get("series_palette", ["#C24141"])
        color = palette[self._index % len(palette)]
        border = self._tokens.get("border_control", "#999")
        radius = self._tokens.get("radius_swatch", 4)
        self._swatch.setStyleSheet(
            f"background-color: {color}; border: 1px solid {border}; border-radius: {radius}px;"
        )
        if self.error_bars_check is not None and self.error_bars_check.isChecked():
            self._error_status_label.setText("with error bars")
        else:
            self._error_status_label.setText("no error bars")

    def set_tokens(self, tokens: dict) -> None:
        super().set_tokens(tokens)
        self._tokens = tokens
        if self._collapsed:
            self._refresh_summary()

    # -- Everything below is unchanged from the pre-redesign implementation --

    def _set_error_controls_visible(self, *, visible: bool):
        for error_role in ("x_error", "y_error"):
            getattr(self, f"_{error_role}_label").setVisible(visible)
            self._role_combos[error_role].setVisible(visible)
        self.error_asymmetric_check.setVisible(visible)
        self._update_minus_controls_visible()

    def _update_minus_controls_visible(self):
        show_minus = self.error_bars_check.isChecked() and self.error_asymmetric_check.isChecked()
        for error_role in ("x_error_minus", "y_error_minus"):
            getattr(self, f"_{error_role}_label").setVisible(show_minus)
            self._role_combos[error_role].setVisible(show_minus)

    def _on_error_bars_toggled(self, checked: bool):  # noqa: FBT001 - Qt `toggled` callback, invoked positionally
        self._set_error_controls_visible(visible=checked)
        self.configChanged.emit()

    def _on_error_symmetry_toggled(self, checked: bool):  # noqa: FBT001 - Qt `toggled` callback, invoked positionally
        """Mirrors data_tab.py's _on_error_symmetry_toggled: default each
        newly-shown minus combo to its plus-side sibling's current
        selection, so ticking the checkbox doesn't silently zero out the
        lower error bar."""
        if checked:
            for minus_role, plus_role in (("x_error_minus", "x_error"), ("y_error_minus", "y_error")):
                minus_combo = self._role_combos[minus_role]
                plus_combo = self._role_combos[plus_role]
                if not minus_combo.currentData():
                    index = minus_combo.findData(plus_combo.currentData())
                    if index >= 0:
                        minus_combo.setCurrentIndex(index)
        self._update_minus_controls_visible()
        self.configChanged.emit()

    def _on_dataset_changed(self):
        dataset_id = self.dataset_combo.currentData()
        if dataset_id:
            self.datasetChanged.emit(dataset_id)
        self.configChanged.emit()

    def set_datasets(self, datasets: list[tuple[str, str]]) -> None:
        """`datasets` is a list of (dataset_id, display_name)."""
        self.dataset_combo.blockSignals(True)  # noqa: FBT003 - Qt method, no keyword args
        try:
            self.dataset_combo.clear()
            for dataset_id, name in datasets:
                self.dataset_combo.addItem(name, dataset_id)
        finally:
            self.dataset_combo.blockSignals(False)  # noqa: FBT003 - Qt method, no keyword args

    def set_dataset_columns(self, dataset_id: str, columns: list[tuple[str, str]]) -> None:
        """`columns` is a list of (column_id, display_name) for `dataset_id`.

        Populates every role combo (including error-column combos) the same
        way; a no-op if `dataset_id` isn't the currently selected dataset.
        """
        if self.dataset_combo.currentData() != dataset_id:
            return
        for combo in self._role_combos.values():
            combo.blockSignals(True)  # noqa: FBT003 - Qt method, no keyword args
            try:
                combo.clear()
                combo.addItem("", "")
                for column_id, name in columns:
                    combo.addItem(name, column_id)
            finally:
                combo.blockSignals(False)  # noqa: FBT003 - Qt method, no keyword args

    def get_series_config(self) -> dict:
        config = {
            "dataset_id": self.dataset_combo.currentData() or "",
            "x_column_id": "",
            "y_column_id": "",
            "x_error_column_id": "",
            "y_error_column_id": "",
            "x_error_minus_column_id": "",
            "y_error_minus_column_id": "",
            "error_symmetric": True,
            "z_column_id": "",
        }
        for role in self._role_spec.roles:
            config[_ROLE_TO_FIELD[role]] = self._role_combos[role].currentData() or ""
        if self.error_bars_check is not None and self.error_bars_check.isChecked():
            config["x_error_column_id"] = self._role_combos["x_error"].currentData() or ""
            config["y_error_column_id"] = self._role_combos["y_error"].currentData() or ""
            config["error_symmetric"] = not self.error_asymmetric_check.isChecked()
            if self.error_asymmetric_check.isChecked():
                config["x_error_minus_column_id"] = self._role_combos["x_error_minus"].currentData() or ""
                config["y_error_minus_column_id"] = self._role_combos["y_error_minus"].currentData() or ""
        return config

    def get_display_names(self) -> dict[str, str]:
        """Display names (not ids) for roles that currently have a selection.

        Mirrors `get_series_config()`'s role handling but returns the combo's
        current text instead of its id -- used only to seed human-readable
        defaults (e.g. axis-label suggestions in the wizard's Labels step),
        never as a source of truth for a persisted column reference.
        """
        names: dict[str, str] = {}
        for role in self._role_spec.roles:
            combo = self._role_combos[role]
            if combo.currentData():
                names[role] = combo.currentText()
        return names

    def is_complete(self) -> bool:
        if not self.dataset_combo.currentData():
            return False
        for role in self._role_spec.required_roles:
            if not self._role_combos[role].currentData():
                return False
        return True

    def apply_picked_columns(self, role: str, column_ids: list[str]) -> None:
        if not column_ids or role not in self._role_combos:
            return
        combo = self._role_combos[role]
        index = combo.findData(column_ids[0])
        if index >= 0:
            combo.setCurrentIndex(index)
