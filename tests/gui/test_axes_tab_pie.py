"""The Axes tab and the Style tab's "Axes" entry for a chart type with no
axes at all (ChartTypeSpec.has_axes -- Pie, #397)."""
import types

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.axes_tab import AxesTab
from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.project.items.chart import Chart


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _axes_tab() -> AxesTab:
    tab = AxesTab(types.SimpleNamespace(app_state=types.SimpleNamespace(current_project=None)))
    # isVisible() only reports truthfully once a top-level ancestor is shown.
    tab.show()
    return tab


def test_a_pie_chart_hides_every_axis_control_and_says_why():
    tab = _axes_tab()

    tab.load(Chart(name="Pie", chart_type=ChartType.PIE))

    assert tab.axis_chips.isVisible() is False
    assert tab._axis_form_container.isVisible() is False
    assert tab.view_card.isVisible() is False
    assert tab.no_axes_label.isVisible() is True


def test_switching_back_to_an_xy_chart_restores_the_axis_controls():
    tab = _axes_tab()
    tab.load(Chart(name="Pie", chart_type=ChartType.PIE))

    tab.refresh_axis_chips(Chart(name="Line", chart_type=ChartType.LINE))

    assert tab.axis_chips.isVisible() is True
    assert tab._axis_form_container.isVisible() is True
    assert tab.no_axes_label.isVisible() is False


def test_a_histogram_keeps_its_axes():
    """Hist has no X *column*, but still two meaningful axes (binned
    values and their counts) -- needs_x_column=False must not be confused
    with having no axes."""
    tab = _axes_tab()

    tab.load(Chart(name="Hist", chart_type=ChartType.HIST))

    assert tab.axis_chips.isVisible() is True
    assert tab.no_axes_label.isVisible() is False


def test_cleared_tab_shows_the_axis_controls():
    tab = _axes_tab()
    tab.load(Chart(name="Pie", chart_type=ChartType.PIE))

    tab.clear()

    assert tab.no_axes_label.isVisible() is False


@pytest.mark.parametrize(("chart_type", "has_axes"), [(ChartType.PIE, False), (ChartType.LINE, True)])
def test_style_tab_axes_entry_shows_a_note_instead_of_forms_for_a_pie(chart_type, has_axes):
    tab = StyleTab(app_context=None)
    tab.show()
    tab.set_chart_type(chart_type)

    tab._on_chip_selected("axes")

    assert tab.axes_style_selector.isVisible() is has_axes
    assert tab.no_axes_style_label.isVisible() is (not has_axes)
