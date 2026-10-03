"""Wizard for assigning experimental column roles and previewing summaries."""

import re
from collections import Counter
from typing import override

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QWizard,
)

from pandaplot.gui.core.widget_extension import PWizard, PWizardPage
from pandaplot.models.project.items.column_role import ColumnRole
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.measurement_analysis import MeasurementAnalysisResult, MeasurementAnalysisService
from pandaplot.services.theme.theme_manager import ThemeManager

_ROLE_OPTIONS: tuple[tuple[str, ColumnRole | None], ...] = (
    ("Unused", None),
    ("Controlled", ColumnRole.CONTROLLED),
    ("Fixed", ColumnRole.FIXED),
    ("Measured", ColumnRole.MEASURED),
)


class _ColumnRolesPage(PWizardPage):
    """Choose one experimental role for every column."""

    def __init__(self, app_context: AppContext, dataset: Dataset, parent: QWidget | None = None):
        self.dataset = dataset
        self._role_combos: dict[str, QComboBox] = {}
        self._group_edits: dict[str, QLineEdit] = {}
        super().__init__(app_context=app_context, parent=parent)
        self._initialize()

    @override
    def _init_ui(self) -> None:
        self.setTitle("Assign column roles")
        self.setSubTitle(
            "Choose the columns that define experimental groups and the numeric "
            "measurements to summarize. Give replicate columns the same measured-variable "
            "name. Fixed columns must have one observed value."
        )
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Suggested roles are inferred from names and values. Review or change them before continuing."))

        self.table = QTableWidget(len(self.dataset.data.columns), 4)
        self.table.setHorizontalHeaderLabels(["Column", "Data type", "Role", "Measured variable"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)

        group_suggestions = self._suggest_measurement_groups()
        role_suggestions = self._suggest_column_roles(group_suggestions)
        for row, column in enumerate(self.dataset.data.columns):
            column_name = str(column)
            column_id = self.dataset.column_id(column_name)
            name_item = QTableWidgetItem(column_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            dtype_item = QTableWidgetItem(str(self.dataset.data[column].dtype))
            dtype_item.setFlags(dtype_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, dtype_item)

            role_combo = QComboBox()
            role_combo.setAccessibleName(f"Role for column {column_name}")
            for label, role in _ROLE_OPTIONS:
                role_combo.addItem(label, role.value if role is not None else "")
            saved_role = self.dataset.column_roles.get(column_id)
            suggested_role = saved_role or role_suggestions.get(column_name)
            saved_value = suggested_role.value if suggested_role is not None else ""
            selected_index = role_combo.findData(saved_value)
            role_combo.setCurrentIndex(max(0, selected_index))
            role_combo.currentIndexChanged.connect(
                lambda index, cid=column_id: self._on_role_changed(cid, index)
            )
            self._role_combos[column_id] = role_combo
            self.table.setCellWidget(row, 2, role_combo)

            group_edit = QLineEdit(
                self.dataset.column_measurement_groups.get(column_id, group_suggestions[column_name])
            )
            group_edit.setAccessibleName(f"Measured variable for column {column_name}")
            group_edit.setPlaceholderText("Same name combines replicate columns")
            group_edit.setEnabled(suggested_role is ColumnRole.MEASURED)
            group_edit.textChanged.connect(self._on_group_name_changed)
            self._group_edits[column_id] = group_edit
            self.table.setCellWidget(row, 3, group_edit)

        layout.addWidget(self.table, 1)

    @override
    def _apply_theme(self) -> None:
        return

    def selected_roles(self) -> dict[str, ColumnRole]:
        """Return the non-unused role assignments keyed by stable column id."""
        roles: dict[str, ColumnRole] = {}
        for column_id, combo in self._role_combos.items():
            value = combo.currentData()
            if value:
                roles[column_id] = ColumnRole(value)
        return roles

    def selected_measurement_groups(self) -> dict[str, str]:
        """Return names for measured columns, keyed by stable column id."""
        return {
            column_id: edit.text().strip()
            for column_id, edit in self._group_edits.items()
            if self._role_combos[column_id].currentData() == ColumnRole.MEASURED.value
        }

    def _on_role_changed(self, column_id: str, _index: int) -> None:
        self._group_edits[column_id].setEnabled(
            self._role_combos[column_id].currentData() == ColumnRole.MEASURED.value
        )
        self.completeChanged.emit()

    def _on_group_name_changed(self, _text: str) -> None:
        self.completeChanged.emit()

    def _suggest_measurement_groups(self) -> dict[str, str]:
        """Suggest a shared name for columns differing only by a numeric suffix."""
        columns = [str(column) for column in self.dataset.data.columns]
        bases = {
            column: re.sub(r"[\s_-]*\d+$", "", column).strip()
            for column in columns
        }
        counts: dict[str, int] = {}
        for base in bases.values():
            if base and base not in columns:
                counts[base] = counts.get(base, 0) + 1
        return {
            column: base if base and counts.get(base, 0) > 1 else column
            for column, base in bases.items()
        }

    def _suggest_column_roles(self, group_suggestions: dict[str, str]) -> dict[str, ColumnRole]:
        """Infer likely roles from repeated-column names, dtypes, and values."""
        columns = [str(column) for column in self.dataset.data.columns]
        measured_groups = Counter(group_suggestions.values())
        replicated_columns = {
            column for column, group_name in group_suggestions.items()
            if measured_groups[group_name] > 1
        }
        numeric_columns = {
            column for column in columns
            if pd.to_numeric(self.dataset.data[column], errors="coerce").notna().any()
        }
        suggestions: dict[str, ColumnRole] = {}
        varying_candidates: list[str] = []

        for column in columns:
            values = self.dataset.data[column].dropna()
            unique_count = values.nunique()
            if unique_count <= 1:
                if not values.empty:
                    suggestions[column] = ColumnRole.FIXED
            elif column in replicated_columns:
                suggestions[column] = ColumnRole.MEASURED
            elif column in numeric_columns:
                varying_candidates.append(column)

        if replicated_columns:
            suggestions.update({
                column: ColumnRole.CONTROLLED
                for column in varying_candidates
            })
        elif varying_candidates:
            controlled_column = max(
                varying_candidates,
                key=lambda column: (self.dataset.data[column].nunique(dropna=True), -columns.index(column)),
            )
            suggestions[controlled_column] = ColumnRole.CONTROLLED
            suggestions.update({
                column: ColumnRole.MEASURED
                for column in varying_candidates
                if column != controlled_column
            })
        return suggestions

    @override
    def isComplete(self) -> bool:
        roles = self.selected_roles()
        groups = self.selected_measurement_groups()
        return (
            ColumnRole.CONTROLLED in roles.values()
            and ColumnRole.MEASURED in roles.values()
            and all(groups.get(column_id) for column_id, role in roles.items() if role is ColumnRole.MEASURED)
        )


class _SummaryPreviewPage(PWizardPage):
    """Preview the grouped statistics and the exclusions before committing."""

    def __init__(self, app_context: AppContext, dataset: Dataset, roles_page: _ColumnRolesPage, parent: QWidget | None = None):
        self.dataset = dataset
        self.roles_page = roles_page
        self.result: MeasurementAnalysisResult | None = None
        super().__init__(app_context=app_context, parent=parent)
        self._initialize()

    @override
    def _init_ui(self) -> None:
        self.setTitle("Review summary")
        self.setSubTitle("Check the grouped statistics and data exclusions before creating the result dataset.")
        layout = QVBoxLayout(self)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        form = QFormLayout()
        self.name_edit = QLineEdit(f"{self.dataset.name} - Measurement Summary")
        self.name_edit.setAccessibleName("Result dataset name")
        self.name_edit.textChanged.connect(self._on_name_changed)
        form.addRow("Result dataset name:", self.name_edit)
        layout.addLayout(form)

        self.create_chart_checkbox = QCheckBox("Open the chart wizard after adding the summary dataset")
        self.create_chart_checkbox.setAccessibleName("Create a chart from the summary dataset")
        layout.addWidget(self.create_chart_checkbox)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

    @override
    def _apply_theme(self) -> None:
        return

    @override
    def initializePage(self) -> None:
        try:
            self.result = MeasurementAnalysisService.summarize(
                self.dataset,
                self.roles_page.selected_roles(),
                measurement_groups=self.roles_page.selected_measurement_groups(),
            )
            self._populate_preview()
        except ValueError as error:
            self.result = None
            self.status_label.setText(error.args[0])
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
        self.completeChanged.emit()

    @override
    def isComplete(self) -> bool:
        return self.result is not None and bool(self.name_edit.text().strip())

    def result_name(self) -> str:
        return self.name_edit.text().strip()

    def create_chart_after_creation(self) -> bool:
        """Whether to open the chart wizard after creating the summary dataset."""
        return self.create_chart_checkbox.isChecked()

    def _on_name_changed(self, _text: str) -> None:
        self.completeChanged.emit()

    def _populate_preview(self) -> None:
        if self.result is None:
            return
        self.status_label.setText(self._status_text(self.result))
        preview = self.result.table.head(100)
        self.table.setRowCount(len(preview))
        self.table.setColumnCount(len(preview.columns))
        self.table.setHorizontalHeaderLabels([str(column) for column in preview.columns])
        for row_index, row in enumerate(preview.itertuples(index=False, name=None)):
            for column_index, value in enumerate(row):
                text = self._display_value(value)
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, column_index, item)
        self.table.resizeColumnsToContents()
        if len(self.result.table) > len(preview):
            self.status_label.setText(
                f"{self.status_label.text()}\nPreviewing the first {len(preview)} of {len(self.result.table)} result rows."
            )

    @staticmethod
    def _display_value(value: object) -> str:
        if value is None or value is pd.NA:
            return "n/a"
        if isinstance(value, float):
            return "n/a" if not np.isfinite(value) else f"{value:.6g}"
        return str(value)

    @staticmethod
    def _status_text(result: MeasurementAnalysisResult) -> str:
        messages: list[str] = []
        if result.excluded_control_rows:
            messages.append(
                f"{result.excluded_control_rows} row(s) excluded because a controlled value is missing."
            )
        for column, count in result.fixed_missing_counts:
            messages.append(f"Fixed column '{column}' has {count} missing value(s); observed values agree.")
        for column, count in result.excluded_measurement_counts:
            messages.append(
                f"'{column}': {count} missing, non-numeric, or infinite measurement value(s) excluded."
            )
        return "\n".join(messages) if messages else "No rows or measurement values were excluded."


class MeasurementAnalysisWizard(PWizard):
    """Assign dataset column roles and generate a grouped summary dataset."""

    def __init__(self, app_context: AppContext, dataset: Dataset, parent: QWidget | None = None):
        self.dataset = dataset
        super().__init__(app_context=app_context, parent=parent)
        self._initialize()

    @override
    def _init_ui(self) -> None:
        self.setWindowTitle("Analyze Measurements")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(780, 560)

        self.roles_page = _ColumnRolesPage(self.app_context, self.dataset)
        self.preview_page = _SummaryPreviewPage(self.app_context, self.dataset, self.roles_page)
        self.addPage(self.roles_page)
        self.addPage(self.preview_page)
        self.restart()

    @override
    def _apply_theme(self) -> None:
        palette = self.app_context.get_manager(ThemeManager).get_surface_palette()
        background = palette.get("card_bg", "#ffffff")
        foreground = palette.get("base_fg", "#202124")
        border = palette.get("card_border", "#d0d0d0")
        input_background = palette.get("card_hover", "#f3f3f3")
        accent = palette.get("accent", "#4A90E2")
        self.setStyleSheet(f"""
            QWizard, QWizardPage {{
                background-color: {background};
                color: {foreground};
            }}
            QLabel, QTableWidget {{
                color: {foreground};
            }}
            QLineEdit, QComboBox, QTableWidget {{
                background-color: {input_background};
                border: 1px solid {border};
                padding: 4px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {accent};
            }}
        """)

    def selected_roles(self) -> dict[str, ColumnRole]:
        """Return roles selected on the first wizard page."""
        return self.roles_page.selected_roles()

    def selected_measurement_groups(self) -> dict[str, str]:
        """Return measured-variable names selected on the first wizard page."""
        return self.roles_page.selected_measurement_groups()

    def result_name(self) -> str:
        """Return the user-selected result dataset name."""
        return self.preview_page.result_name()

    def create_chart_after_creation(self) -> bool:
        """Whether to continue to chart creation after adding the summary."""
        return self.preview_page.create_chart_after_creation()
