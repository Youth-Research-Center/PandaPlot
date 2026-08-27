"""Regression tests: disabling the Legend tab's "Show legend" or "Show
Frame" toggles must hide their dependent controls entirely instead of just
greying them out -- reported live: "in legend tab, if I disable show
frame, I can still see controls and edit them, similarly if I disable
show legend I can still see all of the legend options."
"""
import sys

from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.legend_tab import LegendTab
from pandaplot.models.project.items.chart import Chart


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _chart():
    return Chart(name="C", chart_type="line")


def test_disabling_show_legend_hides_legend_and_frame_sections():
    _qapp()
    legend_tab = LegendTab()
    legend_tab.show()
    legend_tab.load(_chart())

    assert legend_tab.legend_group.isVisible() is True
    assert legend_tab.frame_card.isVisible() is True

    legend_tab.show_legend_toggle.setChecked(checked=False)

    assert legend_tab.legend_group.isVisible() is False
    assert legend_tab.frame_card.isVisible() is False

    legend_tab.show_legend_toggle.setChecked(checked=True)

    assert legend_tab.legend_group.isVisible() is True
    assert legend_tab.frame_card.isVisible() is True


def test_disabling_show_frame_hides_the_frame_option_rows():
    _qapp()
    legend_tab = LegendTab()
    legend_tab.show()
    legend_tab.load(_chart())

    assert legend_tab.legend_bg_color_row.isVisible() is True
    assert legend_tab.legend_bg_opacity_slider.isVisible() is True

    legend_tab.legend_show_frame_toggle.setChecked(checked=False)

    assert legend_tab.legend_bg_color_row.isVisible() is False
    assert legend_tab.legend_bg_opacity_slider.isVisible() is False
    # The card/header itself stays visible, just greyed (disabled).
    assert legend_tab.frame_card.isVisible() is True
    assert legend_tab.frame_header.isEnabled() is False

    legend_tab.legend_show_frame_toggle.setChecked(checked=True)

    assert legend_tab.legend_bg_color_row.isVisible() is True
    assert legend_tab.legend_bg_opacity_slider.isVisible() is True
    assert legend_tab.frame_header.isEnabled() is True
