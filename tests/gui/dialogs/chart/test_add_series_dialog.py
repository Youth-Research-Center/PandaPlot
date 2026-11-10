"""Tests for AddSeriesDialog. The dialog is never exec()'d; it is driven by setting combos."""
import sys
from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.add_series_dialog import AddSeriesDialog
from pandaplot.models.chart.chart_type_spec import get_chart_type_spec
from pandaplot.models.events.event_types import UIEvents
from pandaplot.models.project.items import Chart, Dataset
from pandaplot.models.project.items.chart import DataSeries
from pandaplot.services.help.help_types import CHART_TOPIC_SERIES
from pandaplot.services.theme.theme_manager import ThemeManager
from tests.gui.dialogs.chart.test_wizard_help import _fake_app_context


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def datasets() -> list[Dataset]:
    return [
        Dataset(id="ds-1", name="Sales", data=pd.DataFrame({"date": [1, 2], "revenue": [3, 4], "cost": [5, 6]})),
        Dataset(id="ds-2", name="Weather", data=pd.DataFrame({"temp": [1, 2], "rain": [3, 4]})),
    ]


@pytest.fixture
def project(datasets):
    project = Mock()
    by_id = {d.id: d for d in datasets}
    project.find_item.side_effect = by_id.get
    project.get_all_items.return_value = datasets
    return project


def _cid(dataset: Dataset, name: str) -> str:
    column_id = dataset.column_id(name)
    assert column_id
    return column_id


def _make(qtbot, project, chart_type: str = "line", *, series_datasets: tuple[str, ...] = ()) -> AddSeriesDialog:
    chart = Chart(name="Revenue", chart_type=chart_type)
    for dataset_id in series_datasets:
        chart.data_series.append(DataSeries(dataset_id=dataset_id))
    dialog = AddSeriesDialog(_fake_app_context(), chart=chart, project=project)
    qtbot.addWidget(dialog)
    return dialog


def _pick(dialog: AddSeriesDialog, role: str, column_id: str) -> None:
    combo = dialog.card._role_combos[role]
    combo.setCurrentIndex(combo.findData(column_id))


def _help_topics(dialog: AddSeriesDialog) -> list[str]:
    emit: Mock = dialog.app_context.event_bus.emit  # ty: ignore[invalid-assignment]
    return [call.args[1]["topic_id"] for call in emit.call_args_list if call.args[0] == UIEvents.HELP_REQUESTED]


def test_title_and_heading(qtbot, project):
    dialog = _make(qtbot, project)

    assert dialog.windowTitle() == "Add Series"
    assert dialog.heading_label.text() == "Add a series to Revenue"


@pytest.mark.parametrize(
    "chart_type", ["line", "hist", "pie", "vector", "heatmap", "scatter3d"],
)
def test_card_shows_the_roles_of_the_chart_type(qtbot, project, chart_type):
    dialog = _make(qtbot, project, chart_type)

    assert set(dialog.card._role_combos) >= set(get_chart_type_spec(chart_type).roles)
    assert dialog.card.dataset_combo.count() == 2
    for role in get_chart_type_spec(chart_type).roles:
        assert dialog.card._role_combos[role].currentData() == ""


def test_card_is_standalone(qtbot, project):
    dialog = _make(qtbot, project)
    dialog.show()

    assert not dialog.card.remove_button.isVisible()
    assert not dialog.card._collapse_button.isVisible()
    assert not dialog.card._summary_row.isVisible()


def test_columns_fill_for_the_prefilled_dataset(qtbot, project, datasets):
    dialog = _make(qtbot, project)

    combo = dialog.card.y_column_combo
    assert [combo.itemText(i) for i in range(combo.count())] == ["", "date", "revenue", "cost"]


def test_columns_refill_when_dataset_changes(qtbot, project, datasets):
    dialog = _make(qtbot, project)

    dialog.card.dataset_combo.setCurrentIndex(dialog.card.dataset_combo.findData("ds-2"))

    combo = dialog.card.y_column_combo
    assert [combo.itemText(i) for i in range(combo.count())] == ["", "temp", "rain"]


def test_add_disabled_until_dataset_and_required_roles_chosen(qtbot, project, datasets):
    dialog = _make(qtbot, project)
    assert dialog.add_button.isEnabled() is False
    assert dialog.add_button.toolTip() == "Choose: Y column"

    _pick(dialog, "y", _cid(datasets[0], "revenue"))

    assert dialog.add_button.isEnabled() is True
    assert dialog.add_button.toolTip() == "Add this series to the chart"


def test_tooltip_lists_every_missing_required_role(qtbot, project):
    dialog = _make(qtbot, project, "heatmap")

    assert dialog.add_button.toolTip() == "Choose: X column, Y column, Z column"


def test_tooltip_asks_for_a_dataset_when_there_are_none(qtbot):
    project = Mock()
    project.find_item.return_value = None
    project.get_all_items.return_value = []
    dialog = _make(qtbot, project)

    assert dialog.add_button.isEnabled() is False
    assert dialog.add_button.toolTip() == "Choose a dataset"


def test_prefill_uses_last_non_fit_series_dataset(qtbot, project):
    chart = Chart(name="C", chart_type="line")
    chart.data_series.append(DataSeries(dataset_id="ds-2"))
    chart.data_series.append(DataSeries(dataset_id="ds-1"))
    fit = DataSeries(dataset_id="ds-1")
    fit.series_type = fit.series_type.FIT
    chart.data_series.append(fit)
    chart.data_series.insert(1, DataSeries(dataset_id="ds-2"))
    chart.data_series[-1] = DataSeries(dataset_id="ds-2")
    dialog = AddSeriesDialog(_fake_app_context(), chart=chart, project=project)
    qtbot.addWidget(dialog)

    assert dialog.card.dataset_combo.currentData() == "ds-2"


def test_prefill_skips_fit_series(qtbot, project):
    from pandaplot.models.chart.series_type import SeriesType

    chart = Chart(name="C", chart_type="line")
    chart.data_series.append(DataSeries(dataset_id="ds-2"))
    chart.data_series.append(DataSeries(dataset_id="ds-1", series_type=SeriesType.FIT))
    dialog = AddSeriesDialog(_fake_app_context(), chart=chart, project=project)
    qtbot.addWidget(dialog)

    assert dialog.card.dataset_combo.currentData() == "ds-2"


def test_prefill_falls_back_to_first_dataset_when_series_dataset_is_gone(qtbot, project):
    dialog = _make(qtbot, project, series_datasets=("deleted",))

    assert dialog.card.dataset_combo.currentData() == "ds-1"


def test_prefill_defaults_to_first_dataset_for_an_empty_chart(qtbot, project):
    dialog = _make(qtbot, project)

    assert dialog.card.dataset_combo.currentData() == "ds-1"


def test_series_config_matches_the_card(qtbot, project, datasets):
    dialog = _make(qtbot, project)
    _pick(dialog, "x", _cid(datasets[0], "date"))
    _pick(dialog, "y", _cid(datasets[0], "revenue"))

    config = dialog.series_config()

    assert config == dialog.card.get_series_config()
    assert config["dataset_id"] == "ds-1"
    assert config["x_column_id"] == _cid(datasets[0], "date")
    assert config["y_column_id"] == _cid(datasets[0], "revenue")


def test_add_accepts_and_cancel_rejects(qtbot, project, datasets):
    dialog = _make(qtbot, project)
    _pick(dialog, "y", _cid(datasets[0], "revenue"))
    dialog.add_button.click()
    assert dialog.result() == dialog.DialogCode.Accepted

    other = _make(qtbot, project)
    other.cancel_button.click()
    assert other.result() == other.DialogCode.Rejected


def test_add_is_the_default_button(qtbot, project):
    dialog = _make(qtbot, project)

    assert dialog.add_button.isDefault()
    assert not dialog.cancel_button.autoDefault()


def test_buttons_have_accessible_names(qtbot, project):
    dialog = _make(qtbot, project)

    assert dialog.accessibleName() == "Add Series"
    assert dialog.add_button.accessibleName()
    assert dialog.cancel_button.accessibleName()
    assert dialog.help_button.accessibleName()


def test_help_button_publishes_series_topic(qtbot, project):
    dialog = _make(qtbot, project)

    dialog.help_button.click()

    assert _help_topics(dialog) == [CHART_TOPIC_SERIES]


@pytest.mark.skipif(sys.platform == "darwin", reason="F1 is Cmd+? on macOS, so QKeySequence.HelpContents differs")
def test_f1_publishes_series_topic(qtbot, project):
    dialog = _make(qtbot, project)
    dialog.show()
    assert QTest.qWaitForWindowActive(dialog)

    QTest.keyClick(dialog, Qt.Key.Key_F1)

    assert _help_topics(dialog) == [CHART_TOPIC_SERIES]


def test_stylesheet_is_scoped_to_the_card_not_the_dialog(qtbot, project):
    dialog = _make(qtbot, project)
    sheet = dialog.styleSheet()

    assert "AddSeriesDialog {" in sheet
    assert "SeriesConfigCard QLabel" in sheet
    assert "AddSeriesDialog QLabel" not in sheet
    assert sheet.count("AddSeriesDialog") == 1


@pytest.mark.parametrize("dark", [False, True])
def test_theming_in_light_and_dark(qtbot, project, dark):
    dialog = _make(qtbot, project)
    theme_manager = dialog.app_context.get_manager(ThemeManager)
    theme_manager.get_surface_palette.return_value = (
        {"card_bg": "#101010", "base_fg": "#f0f0f0", "card_hover": "#202020", "card_border": "#444", "accent": "#0af"}
        if dark
        else {"card_bg": "#fafafa", "base_fg": "#101010"}
    )

    dialog._apply_theme()

    assert theme_manager.get_surface_palette.return_value["card_bg"] in dialog.styleSheet()
