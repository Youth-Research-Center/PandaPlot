"""StyleTab's "Fill to" selector: plain series labels with series/fit icons, selected by value (#586)."""
from unittest.mock import Mock

import numpy as np
import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.series_source_picker import FIT_ICON_NAME, SERIES_ICON_NAME
from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.gui.resources.themed_icons import themed_icon
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_style import LineSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart, DataSeries
from pandaplot.models.state.app_context import AppContext
from tests.gui.icon_testing import ICON_TOKENS, fresh_icon_tokens

ICON_SIZE = QSize(16, 16)


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def tokens() -> dict[str, str]:
    return fresh_icon_tokens()


@pytest.fixture
def app_context(tokens):
    context = Mock(spec=AppContext)
    context.event_bus = Mock()
    context.get_manager.return_value.get_design_tokens.side_effect = lambda: dict(tokens)
    return context


def _line(label: str, **style_fields) -> DataSeries:
    return DataSeries(dataset_id="ds1", x_column="x", y_column="y", series_type=SeriesType.LINE, label=label, style=LineSeriesStyle(**style_fields))


def _fit(label: str) -> DataSeries:
    chart = Chart(name="C", chart_type="line")
    chart.add_fit_series("ds1", x_data=np.array([1.0, 2.0]), y_data=np.array([1.0, 2.0]), label=label, style=FitStyle(fit_type="linear"))
    fit = chart.data_series[0]
    assert fit.is_fit
    return fit


def _tab(app_context, series_list: list[DataSeries]) -> StyleTab:
    tab = StyleTab(app_context=app_context)
    tab.set_chart_type(ChartType.LINE)
    tab.set_series_list(series_list, selected_index=0)
    tab.set_selected("series", series_list[0])
    return tab


def _icon_image(icon):
    return icon.pixmap(ICON_SIZE).toImage()


def _items(tab: StyleTab) -> list[tuple[str, object]]:
    combo = tab.fill_to_control
    return [(combo.itemText(row), combo.itemData(row)) for row in range(combo.count())]


def test_fill_to_items_are_plain_labels_without_the_arrow_prefix(app_context):
    first, second, fit = _line("First"), _line("Second"), _fit("A Fit")

    tab = _tab(app_context, [first, second, fit])

    assert _items(tab) == [("Baseline", -1), ("Second", 1), ("A Fit", 2)]


def test_fill_to_unlabelled_series_fall_back_to_their_position(app_context):
    first, unlabelled = _line("First"), _line("")

    tab = _tab(app_context, [first, unlabelled])

    assert _items(tab) == [("Baseline", -1), ("Series 2", 1)]


def test_fill_to_items_carry_series_and_fit_icons_and_baseline_has_none(app_context):
    first, second, fit = _line("First"), _line("Second"), _fit("A Fit")

    tab = _tab(app_context, [first, second, fit])

    combo = tab.fill_to_control
    assert combo.itemIcon(0).isNull()
    assert _icon_image(combo.itemIcon(1)) == _icon_image(themed_icon(app_context, SERIES_ICON_NAME))
    assert _icon_image(combo.itemIcon(2)) == _icon_image(themed_icon(app_context, FIT_ICON_NAME))
    assert SERIES_ICON_NAME == "chart-line"


def test_fill_to_selection_round_trips_by_value_not_by_label(app_context):
    first, second = _line("First"), _line("Second", fill_to_index=1, fill_enabled=True)

    tab = _tab(app_context, [second, first])
    tab.load_series_style(second)

    assert tab.fill_to_control.currentValue() == 1
    assert tab.fill_to_control.currentText() == "First"


def test_fill_to_icons_retint_when_the_theme_changes(app_context, tokens):
    first, second, fit = _line("First"), _line("Second"), _fit("A Fit")
    tab = _tab(app_context, [first, second, fit])
    tokens.update(text_primary="#E2E2E2", text_disabled="#5B6270")

    tab.apply_theme(dict(tokens))

    combo = tab.fill_to_control
    assert _icon_image(combo.itemIcon(1)) == _icon_image(themed_icon(app_context, SERIES_ICON_NAME))
    assert _icon_image(combo.itemIcon(1)) != _icon_image(
        themed_icon(Mock(**{"get_manager.return_value.get_design_tokens.return_value": dict(ICON_TOKENS)}), SERIES_ICON_NAME),
    )
    assert combo.itemIcon(0).isNull()


def test_apply_theme_without_an_app_context_does_not_touch_the_fill_to_icons():
    tab = StyleTab(app_context=None)

    tab.apply_theme(fresh_icon_tokens())

    assert tab.fill_to_control.itemIcon(0).isNull()
