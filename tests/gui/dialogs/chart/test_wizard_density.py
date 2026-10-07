"""Tests for the chart wizard's Density (KDE) support (#398).

Density reuses Histogram's single "values" role (mapped onto y_column_id
by SeriesConfigCard's _ROLE_TO_FIELD), so the Data step needs no new
wiring -- these pin that, plus the Labels step's preview and label seeding.
"""
import sys

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas
from pandaplot.gui.dialogs.chart.series_config_card import SeriesConfigCard
from pandaplot.gui.dialogs.chart.wizard_preview import render_wizard_preview
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.project import Project
from tests.gui.dialogs.chart.test_chart_wizard import _make_wizard


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _project_with(values: list[float]) -> tuple[Project, Dataset]:
    project = Project(name="Density Preview Project")
    dataset = Dataset(name="ds1", data=pd.DataFrame({"v": values}))
    project.add_item(dataset)
    return project, dataset


def test_density_config_card_asks_for_values_only():
    card = SeriesConfigCard(CHART_TYPE_SPECS[ChartType.DENSITY])

    assert set(card._role_combos) == {"values"}
    assert card.error_bars_check is None


def test_density_config_card_maps_values_onto_y_column_id():
    card = SeriesConfigCard(CHART_TYPE_SPECS[ChartType.DENSITY])
    card.set_datasets([("ds-1", "ds1")])
    card.set_dataset_columns("ds-1", [("col-v", "v")])
    assert card.is_complete() is False

    card.apply_picked_columns("values", ["col-v"])

    assert card.is_complete() is True
    config = card.get_series_config()
    assert config["y_column_id"] == "col-v"
    assert config["x_column_id"] == ""


def test_a_configured_density_series_renders_its_kde_in_the_labels_preview():
    canvas = ChartCanvas(width=4, height=3, dpi=80)
    values = np.random.default_rng(1).normal(size=50).tolist()
    project, dataset = _project_with(values)

    render_wizard_preview(canvas, project, "density",
                          [{"dataset_id": dataset.id, "y_column_id": dataset.column_id("v")}],
                          "Title", "", "v", "Density", show_legend=True, show_grid=True)

    lines = canvas.axes.get_lines()
    assert len(lines) == 1
    # The real KDE, not the 5-point sample fallback: its grid spans the
    # picked column's own range, padded past both ends.
    assert lines[0].get_xdata()[0] < min(values)
    assert lines[0].get_xdata()[-1] > max(values)


def test_a_constant_density_series_falls_back_to_the_sample_preview():
    """gaussian_kde can't estimate a constant column -- the preview must
    still show a density curve rather than empty (or crashed) axes."""
    canvas = ChartCanvas(width=4, height=3, dpi=80)
    project, dataset = _project_with([3.0, 3.0, 3.0])

    render_wizard_preview(canvas, project, "density",
                          [{"dataset_id": dataset.id, "y_column_id": dataset.column_id("v")}],
                          "Title", "", "v", "Density", show_legend=True, show_grid=True)

    assert len(canvas.axes.get_lines()) == 1


def test_density_seeds_the_values_column_as_x_and_density_as_y():
    wizard = _make_wizard(initial_title="Chart from Sales", initial_dataset_id="ds-1",
                          initial_column_ids=["col-rev"])
    density_row = next(
        row for row in range(wizard.type_page.type_list.count())
        if wizard.type_page.type_list.item(row).data(Qt.ItemDataRole.UserRole) == "density"
    )
    wizard.type_page.type_list.setCurrentRow(density_row)
    wizard.next()  # Type -> Data: pre-selection fills the Values column
    wizard.next()  # Data -> Labels

    assert wizard.get_series_configs()[0]["y_column_id"] == "col-rev"
    assert wizard.get_x_label() == "Revenue"
    assert wizard.get_y_label() == "Density"
