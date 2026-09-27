"""Tests for StyleTab's Vector3D chart-type support -- its own card, not a
reuse of 2-D Vector's (Axes3D.quiver takes a different keyword set than
2-D quiver and has no per-arrow colormap support, see Vector3DSeriesStyle's
docstring)."""
import sys

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_style import Vector3DSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import DataSeries


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _tab():
    tab = StyleTab(app_context=None)
    tab.show()
    return tab


def test_vector3d_card_is_shown_only_for_a_vector3d_series_target():
    tab = _tab()
    series = DataSeries(dataset_id="ds1", series_type=SeriesType.VECTOR3D)
    tab.set_chart_type(ChartType.VECTOR3D)
    tab.set_selected("series", series)

    assert tab.vector3d_card.isVisible() is True
    assert tab.vector_card.isVisible() is False
    assert tab.line_card.isVisible() is False
    assert tab.marker_card.isVisible() is False
    assert tab.fill_card.isVisible() is False
    assert tab.error_bars_card.isVisible() is False


def test_vector_card_is_hidden_for_a_vector3d_series_target():
    """Regression guard: needs_secondary_columns is true for both Vector
    and Vector3D, so the 2-D Vector card must be gated on something more
    specific than that flag, or it would wrongly reappear here."""
    tab = _tab()
    series = DataSeries(dataset_id="ds1", series_type=SeriesType.VECTOR3D)
    tab.set_chart_type(ChartType.VECTOR3D)

    tab.set_selected("series", series)

    assert tab.vector_card.isVisible() is False


def test_vector3d_card_is_hidden_for_a_vector_series_target():
    tab = _tab()
    series = DataSeries(dataset_id="ds1", series_type=SeriesType.VECTOR)
    tab.set_chart_type(ChartType.VECTOR)

    tab.set_selected("series", series)

    assert tab.vector3d_card.isVisible() is False


def test_apply_series_style_to_writes_vector3d_fields():
    tab = _tab()
    series = DataSeries(dataset_id="ds1", series_type=SeriesType.VECTOR3D)
    tab.set_chart_type(ChartType.VECTOR3D)
    tab.set_selected("series", series)

    tab.vector3d_color_row.setCurrentColor("#123456")
    tab.vector3d_length_slider.setValue(2.5)
    tab.vector3d_arrow_ratio_slider.setValue(0.6)
    tab.vector3d_normalize_toggle.setChecked(checked=True)

    tab.apply_series_style_to(series)

    assert series.style.vector_color == "#123456"
    assert series.style.vector_length == 2.5
    assert series.style.vector_arrow_ratio == 0.6
    assert series.style.vector_normalize is True


def test_load_series_style_populates_vector3d_card_from_series():
    tab = _tab()
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.VECTOR3D,
        style=Vector3DSeriesStyle(
            vector_color="#abcdef", vector_length=3.0,
            vector_arrow_ratio=0.5, vector_normalize=True,
        ),
    )
    tab.set_chart_type(ChartType.VECTOR3D)

    tab.load_series_style(series)

    assert tab.vector3d_color_row.currentColor() == "#abcdef"
    assert tab.vector3d_length_slider.value() == 3.0
    assert tab.vector3d_arrow_ratio_slider.value() == 0.5
    assert tab.vector3d_normalize_toggle.isChecked() is True
