"""The chart wizard's Pie support (#397): the Data step's per-series card
and the Labels step's live preview."""
import sys

import pandas as pd
import pytest
from matplotlib.patches import Wedge
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas
from pandaplot.gui.dialogs.chart.series_config_card import SeriesConfigCard
from pandaplot.gui.dialogs.chart.wizard_preview import render_wizard_preview
from pandaplot.models.chart.chart_type_spec import get_chart_type_spec
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.project import Project


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _wedges(canvas):
    return [patch for patch in canvas.axes.patches if isinstance(patch, Wedge)]


def _pie_card() -> SeriesConfigCard:
    card = SeriesConfigCard(role_spec=get_chart_type_spec("pie"))
    card.set_datasets([("ds-1", "Dataset 1")])
    card.dataset_combo.setCurrentIndex(0)
    card.set_dataset_columns("ds-1", [("col-n", "Name"), ("col-v", "Value")])
    return card


def test_pie_card_offers_a_values_and_an_optional_labels_combo_and_no_x():
    card = _pie_card()

    assert hasattr(card, "values_column_combo")
    assert hasattr(card, "labels_column_combo")
    assert not hasattr(card, "x_column_combo")
    # No error-bars section: a pie can't draw them.
    assert card.error_bars_check is None


def test_pie_card_maps_values_to_y_column_id_and_labels_to_label_column_id():
    card = _pie_card()
    card.values_column_combo.setCurrentIndex(card.values_column_combo.findData("col-v"))
    card.labels_column_combo.setCurrentIndex(card.labels_column_combo.findData("col-n"))

    config = card.get_series_config()

    assert config["y_column_id"] == "col-v"
    assert config["label_column_id"] == "col-n"


def test_pie_card_is_complete_with_values_alone():
    card = _pie_card()
    assert card.is_complete() is False

    card.values_column_combo.setCurrentIndex(card.values_column_combo.findData("col-v"))

    assert card.is_complete() is True


def test_pie_preview_with_no_series_falls_back_to_sample_wedges():
    canvas = ChartCanvas(width=4, height=3, dpi=80)

    render_wizard_preview(canvas, None, "pie", [], "Title", "", "X", "Y", show_legend=True, show_grid=True)

    assert len(_wedges(canvas)) == 5


def test_pie_preview_with_a_configured_series_draws_real_labeled_wedges():
    canvas = ChartCanvas(width=4, height=3, dpi=80)
    project = Project(name="Preview Project")
    dataset = Dataset(name="ds1", data=pd.DataFrame({"name": ["a", "b"], "value": [1, 3]}))
    project.add_item(dataset)
    series_configs = [{
        "dataset_id": dataset.id,
        "x_column_id": "", "y_column_id": dataset.column_id("value"),
        "label_column_id": dataset.column_id("name"),
    }]

    render_wizard_preview(canvas, project, "pie", series_configs, "Title", "", "", "", show_legend=True, show_grid=True)

    assert [wedge.get_label() for wedge in _wedges(canvas)] == ["a", "b"]
