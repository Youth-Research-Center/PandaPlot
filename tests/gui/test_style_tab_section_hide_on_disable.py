"""Regression tests: disabling a style-tab section's on/off toggle
(Marker/Fill/Confidence Band) must hide its option rows entirely, leaving
only the greyed section title -- reported live: "in style selection, if
I disable entire section, such as marker, we should hide options and
just leave the section title with a disabled state, instead of showing
all options in a disabled state."
"""
import sys

import numpy as np
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_style.line import LineSeriesStyle
from pandaplot.models.project.items.chart import DataSeries, FitData


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _line_series():
    return DataSeries(
        dataset_id="ds1", x_column="x", y_column="y", label="Series A",
        style=LineSeriesStyle(),
    )


def _fit_with_confidence(**style_kwargs):
    fit = FitData(
        source_dataset_id="ds1", fit_type="linear",
        x_data=np.array([1.0, 2.0]), y_data=np.array([1.0, 2.0]),
        label="Fit", style=FitStyle(**style_kwargs),
    )
    fit.confidence_lower = np.array([0.5, 1.5])
    fit.confidence_upper = np.array([1.5, 2.5])
    return fit


def test_disabling_markers_hides_the_option_rows():
    _qapp()
    style_tab = StyleTab(app_context=build_app_context())
    style_tab.show()
    style_tab.set_chart_type(ChartType.LINE)
    style_tab.set_selected("series", _line_series())

    style_tab.markers_enabled_toggle.setChecked(checked=True)
    assert style_tab.marker_shape_control.isVisible() is True

    style_tab.markers_enabled_toggle.setChecked(checked=False)

    assert style_tab.marker_shape_control.isVisible() is False
    assert style_tab.marker_size_slider.isVisible() is False
    assert style_tab.marker_color_label.isVisible() is False
    assert style_tab.marker_color_row.isVisible() is False
    # The card/header itself stays visible, just greyed (disabled).
    assert style_tab.marker_card.isVisible() is True
    assert style_tab.marker_header.isEnabled() is False


def test_disabling_fill_hides_the_option_rows():
    _qapp()
    style_tab = StyleTab(app_context=build_app_context())
    style_tab.show()
    style_tab.set_chart_type(ChartType.LINE)
    style_tab.set_selected("series", _line_series())

    style_tab.fill_enabled_toggle.setChecked(checked=True)
    assert style_tab.fill_horizontal_toggle.isVisible() is True
    assert style_tab.fill_opacity_label.isVisible() is True

    style_tab.fill_enabled_toggle.setChecked(checked=False)

    assert style_tab.fill_horizontal_toggle.isVisible() is False
    assert style_tab.fill_to_control.isVisible() is False
    assert style_tab.fill_opacity_slider.isVisible() is False
    assert style_tab.fill_opacity_label.isVisible() is False
    assert style_tab.fill_card.isVisible() is True
    assert style_tab.fill_header.isEnabled() is False


def test_disabling_confidence_band_hides_the_option_rows():
    """Confidence Band currently has no visibility wiring at all for its
    on/off toggle -- this closes that gap using the same hide-on-disable
    convention as Marker/Fill."""
    _qapp()
    style_tab = StyleTab(app_context=build_app_context())
    style_tab.show()
    style_tab.set_selected(
        "fit", _fit_with_confidence(band_fill_enabled=True, band_color="#445566")
    )

    assert style_tab.band_color_row.isVisible() is True

    style_tab.band_enabled_toggle.setChecked(checked=False)

    assert style_tab.band_color_row.isVisible() is False
    assert style_tab.band_match_line_toggle.isVisible() is False
    assert style_tab.band_opacity_slider.isVisible() is False
    assert style_tab.band_card.isVisible() is True
    assert style_tab.band_header.isEnabled() is False
