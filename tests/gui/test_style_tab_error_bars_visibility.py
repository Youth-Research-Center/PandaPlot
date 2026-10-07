"""Regression test: the Style tab's Error Bars card must only show for a
selected series that actually has an error-bar column configured -- not for
every series unconditionally.
"""
import sys

from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style.hist import HistSeriesStyle
from pandaplot.models.chart.series_style.line import LineSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import DataSeries


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_error_bars_card_hidden_when_no_error_columns_configured():
    _qapp()
    app_context = build_app_context()
    style_tab = StyleTab(app_context=app_context)
    style_tab.show()
    style_tab.set_chart_type(ChartType.LINE)

    series = DataSeries(dataset_id="ds1", x_column="x", y_column="y", label="Series A")
    style_tab.set_selected("series", series)

    assert not style_tab.error_bars_card.isVisible()


def test_error_bars_card_visible_when_y_error_column_configured():
    _qapp()
    app_context = build_app_context()
    style_tab = StyleTab(app_context=app_context)
    style_tab.show()
    style_tab.set_chart_type(ChartType.LINE)

    series = DataSeries(
        dataset_id="ds1", x_column="x", y_column="y", label="Series A",
        style=LineSeriesStyle(error_bars=ErrorBarConfig(y_error_column_id="err-col-id")),
    )
    style_tab.set_selected("series", series)

    assert style_tab.error_bars_card.isVisible()


def test_error_bars_card_hidden_for_histogram_series_even_with_error_columns_configured():
    """Regression test for issue #178: a histogram series never renders
    error bars (chart_editor.py's "hist" branch only ever calls
    target_axes.hist(y_data, ...)), so the Error Bars card must stay hidden
    for a hist-typed series regardless of has_error_data -- SERIES_TYPE_SPECS
    marks SeriesType.HIST.supports_error_bars=False for exactly this reason."""
    _qapp()
    app_context = build_app_context()
    style_tab = StyleTab(app_context=app_context)
    style_tab.show()
    style_tab.set_chart_type(ChartType.HIST)

    series = DataSeries(
        dataset_id="ds1", x_column="x", y_column="y", label="Series A",
        series_type=SeriesType.HIST,
        style=HistSeriesStyle(),
    )
    style_tab.set_selected("series", series)

    assert not style_tab.error_bars_card.isVisible()


def test_error_bars_card_hidden_for_fit():
    _qapp()
    app_context = build_app_context()
    style_tab = StyleTab(app_context=app_context)
    style_tab.show()
    style_tab.set_chart_type(ChartType.LINE)

    series = DataSeries(
        dataset_id="ds1", x_column="x", y_column="y", label="Series A",
        style=LineSeriesStyle(error_bars=ErrorBarConfig(y_error_column_id="err-col-id")),
    )
    style_tab.set_selected("series", series)
    assert style_tab.error_bars_card.isVisible()

    import numpy as np

    from pandaplot.models.chart.fit_style import FitStyle
    from pandaplot.models.project.items.chart import Chart
    chart = Chart(name="c", chart_type="line")
    fit = chart.add_fit_series(
        source_dataset_id="ds1",
        x_data=np.array([1.0]), y_data=np.array([2.0]), label="Fit",
        style=FitStyle(fit_type="linear"),
    )
    style_tab.set_selected("series", fit)

    assert not style_tab.error_bars_card.isVisible()
