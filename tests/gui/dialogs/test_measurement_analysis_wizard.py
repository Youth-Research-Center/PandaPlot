"""Tests for the measurement-analysis wizard flow."""

from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.measurement_analysis_wizard import MeasurementAnalysisWizard
from pandaplot.models.project.items import ColumnRole, Dataset
from pandaplot.services.theme.theme_manager import ThemeManager


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_wizard(data: pd.DataFrame, saved_roles: dict[str, ColumnRole] | None = None):
    app_context = Mock()
    app_context.event_bus = Mock()
    theme_manager = Mock(spec=ThemeManager)
    theme_manager.get_surface_palette.return_value = {
        "card_bg": "#ffffff",
        "base_fg": "#202124",
        "card_border": "#d0d0d0",
        "card_hover": "#f3f3f3",
        "accent": "#4A90E2",
    }
    app_context.get_manager.return_value = theme_manager
    dataset = Dataset(name="Experiment", data=data)
    for column, role in (saved_roles or {}).items():
        dataset.set_column_role(dataset.column_id(column), role)
    return MeasurementAnalysisWizard(app_context, dataset), dataset


def _set_role(wizard: MeasurementAnalysisWizard, column: str, role: ColumnRole | None) -> None:
    column_id = wizard.dataset.column_id(column)
    combo = wizard.roles_page._role_combos[column_id]
    value = role.value if role is not None else ""
    combo.setCurrentIndex(combo.findData(value))


def test_role_page_requires_controlled_and_measured_columns_and_previews_summary():
    wizard, _dataset = _make_wizard(pd.DataFrame({"dose": [1, 1], "response": [2.0, 4.0]}))

    assert not wizard.roles_page.isComplete()
    _set_role(wizard, "dose", ColumnRole.CONTROLLED)
    _set_role(wizard, "response", ColumnRole.MEASURED)
    assert wizard.roles_page.isComplete()

    wizard.next()

    assert wizard.currentPage() is wizard.preview_page
    assert wizard.preview_page.isComplete()
    assert wizard.preview_page.result.table.loc[0, "Mean"] == pytest.approx(3)
    assert wizard.result_name() == "Experiment - Measurement Summary"
    plot_button = wizard.button(wizard.WizardButton.CustomButton1)
    assert plot_button.text() == "Plot a Graph"
    assert not plot_button.isHidden()
    assert wizard.plot_requested() is False


def test_plot_a_graph_button_accepts_wizard_and_sets_plot_intent():
    wizard, _dataset = _make_wizard(
        pd.DataFrame({"dose": [1, 1], "response": [2.0, 4.0]}),
        {"dose": ColumnRole.CONTROLLED, "response": ColumnRole.MEASURED},
    )
    wizard.next()
    assert wizard.preview_page.isComplete()
    wizard.show()
    QApplication.processEvents()

    wizard.button(wizard.WizardButton.CustomButton1).click()

    assert wizard.result() == wizard.DialogCode.Accepted
    assert wizard.plot_requested() is True


def test_fixed_column_validation_blocks_preview_until_roles_are_corrected():
    wizard, _dataset = _make_wizard(
        pd.DataFrame({"dose": [1, 1], "device": ["A", "B"], "response": [2.0, 4.0]}),
    )
    _set_role(wizard, "dose", ColumnRole.CONTROLLED)
    _set_role(wizard, "device", ColumnRole.FIXED)
    _set_role(wizard, "response", ColumnRole.MEASURED)

    wizard.next()

    assert wizard.currentPage() is wizard.preview_page
    assert not wizard.preview_page.isComplete()
    assert "multiple observed values" in wizard.preview_page.status_label.text()

    wizard.back()
    _set_role(wizard, "device", None)
    wizard.next()
    assert wizard.preview_page.isComplete()


def test_missing_controlled_values_are_reported_in_preview():
    wizard, _dataset = _make_wizard(
        pd.DataFrame({"dose": [1.0, None], "response": [2.0, 4.0]}),
        {"dose": ColumnRole.CONTROLLED, "response": ColumnRole.MEASURED},
    )

    wizard.next()

    assert "1 row(s) excluded" in wizard.preview_page.status_label.text()
    assert wizard.preview_page.result.excluded_control_rows == 1


def test_numbered_measured_columns_are_suggested_as_replicates():
    wizard, _dataset = _make_wizard(
        pd.DataFrame({
            "Nozzle_Area": [1, 2],
            "Velocity1": [10.0, 6.0],
            "Velocity2": [12.0, 8.0],
            "Velocity3": [8.0, 4.0],
        }),
        {
            "Nozzle_Area": ColumnRole.CONTROLLED,
            "Velocity1": ColumnRole.MEASURED,
            "Velocity2": ColumnRole.MEASURED,
            "Velocity3": ColumnRole.MEASURED,
        },
    )

    assert set(wizard.selected_measurement_groups().values()) == {"Velocity"}
    assert wizard.roles_page.isComplete()
    wizard.next()
    assert wizard.preview_page.result.table["Measured variable"].tolist() == ["Velocity", "Velocity"]
    assert wizard.preview_page.result.table["Count"].tolist() == [3, 3]
    assert wizard.preview_page.result.table["Mean"].tolist() == [10.0, 6.0]


def test_roles_and_replicate_names_are_suggested_for_unannotated_dataset():
    wizard, _dataset = _make_wizard(pd.DataFrame({
        "Nozzle_Area": [0, 1, 2],
        "Velocity1": [0.0, 10.0, 6.0],
        "Velocity2": [0.0, 12.0, 8.0],
        "Velocity3": [0.0, 8.0, 4.0],
        "Velocity4": [0.0, 10.0, 6.0],
        "Velocity5": [0.0, 10.0, 8.0],
    }))

    suggested_roles = wizard.selected_roles()
    assert suggested_roles[wizard.dataset.column_id("Nozzle_Area")] is ColumnRole.CONTROLLED
    assert all(
        suggested_roles[wizard.dataset.column_id(column)] is ColumnRole.MEASURED
        for column in ("Velocity1", "Velocity2", "Velocity3", "Velocity4", "Velocity5")
    )
    assert set(wizard.selected_measurement_groups().values()) == {"Velocity"}

    _set_role(wizard, "Velocity5", None)
    assert wizard.roles_page._role_combos[wizard.dataset.column_id("Velocity5")].currentData() == ""


def test_saved_role_assignments_override_new_suggestions():
    wizard, _dataset = _make_wizard(
        pd.DataFrame({"area": [1, 2], "reading1": [3, 4], "reading2": [5, 6]}),
        {"reading1": ColumnRole.CONTROLLED},
    )

    assert wizard.selected_roles()[wizard.dataset.column_id("reading1")] is ColumnRole.CONTROLLED
