"""Chart wizard coverage for Stacked Bar (#396): its Data-step config card
(spec-driven, identical to Bar's) and both previews actually stacking."""
from unittest.mock import Mock

import pandas as pd
import pytest
from matplotlib.colors import to_hex
from matplotlib.container import BarContainer
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.series_config_card import SeriesConfigCard
from pandaplot.gui.dialogs.chart.wizard_preview import draw_chart_type_sample, render_wizard_preview
from pandaplot.models.chart.chart_type_spec import get_chart_type_spec
from pandaplot.models.chart.series_style_builder import DEFAULT_SERIES_COLORS
from pandaplot.models.project.items import Dataset


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication([])


def _canvas():
    from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas
    return ChartCanvas(width=3, height=2, dpi=60)


def _bar_bottoms(axes) -> list[list[float]]:
    return [[patch.get_y() for patch in c] for c in axes.containers if isinstance(c, BarContainer)]


def test_config_card_asks_for_the_same_roles_as_a_bar_chart():
    card = SeriesConfigCard(role_spec=get_chart_type_spec("stacked_bar"))
    card.set_datasets([("ds-1", "Sales")])
    card.set_dataset_columns("ds-1", [("col-x", "X"), ("col-y", "Y")])

    assert card.is_complete() is False
    card.y_column_combo.setCurrentIndex(card.y_column_combo.findData("col-y"))
    assert card.is_complete() is True
    assert card.get_series_config()["x_column_id"] == ""


def test_type_step_sample_shows_two_stacked_layers():
    """A single layer would look exactly like the Bar sample."""
    canvas = _canvas()

    draw_chart_type_sample(canvas, "stacked_bar")

    first, second = _bar_bottoms(canvas.axes)
    assert first == [0.0] * len(first)
    assert second == [patch.get_height() for patch in canvas.axes.containers[0]]


def test_bar_type_step_sample_is_still_a_single_layer():
    canvas = _canvas()

    draw_chart_type_sample(canvas, "bar")

    assert len(_bar_bottoms(canvas.axes)) == 1


def test_labels_step_preview_stacks_the_configured_series():
    dataset = Mock(spec=Dataset)
    dataset.id = "ds-1"
    dataset.name = "Sales"
    dataset.data = pd.DataFrame({"Q": [1, 2], "A": [10.0, 20.0], "B": [1.0, 2.0]})
    dataset.column_name.side_effect = lambda cid: {"col-q": "Q", "col-a": "A", "col-b": "B"}.get(cid)
    project = Mock()
    project.find_item.return_value = dataset
    canvas = _canvas()

    render_wizard_preview(
        canvas, project, "stacked_bar",
        [{"dataset_id": "ds-1", "x_column_id": "col-q", "y_column_id": y} for y in ("col-a", "col-b")],
        "Title", "", "x", "y", show_legend=True, show_grid=False,
    )

    assert _bar_bottoms(canvas.axes) == [[0.0, 0.0], [10.0, 20.0]]


def test_labels_step_preview_colors_each_series_from_the_default_palette():
    dataset = Mock(spec=Dataset)
    dataset.id = "ds-1"
    dataset.name = "Sales"
    dataset.data = pd.DataFrame({"Q": [1, 2], "A": [10.0, 20.0], "B": [1.0, 2.0]})
    dataset.column_name.side_effect = lambda cid: {"col-q": "Q", "col-a": "A", "col-b": "B"}.get(cid)
    project = Mock()
    project.find_item.return_value = dataset
    canvas = _canvas()

    render_wizard_preview(
        canvas, project, "stacked_bar",
        [{"dataset_id": "ds-1", "x_column_id": "col-q", "y_column_id": y} for y in ("col-a", "col-b")],
        "Title", "", "x", "y", show_legend=True, show_grid=False,
    )

    bar_containers = [c for c in canvas.axes.containers if isinstance(c, BarContainer)]
    assert [to_hex(c.patches[0].get_facecolor()) for c in bar_containers] == list(DEFAULT_SERIES_COLORS[:2])
