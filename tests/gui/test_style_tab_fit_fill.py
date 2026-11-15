"""The Style tab's Fill card for a FIT series (#431): visible for fits, loaded
from and applied to FitStyle's shared area-fill fields, independent of the
Confidence Band card, with sections addressing the fit's curve points."""
import sys

import numpy as np
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.project.items.chart import Chart

CURVE_POINTS = 50


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _chart_with_fit(**style_kwargs) -> tuple[Chart, object]:
    chart = Chart(name="c", chart_type="line")
    series = chart.add_data_series("ds1", x_column="x", y_column="y", label="Data")
    x = np.linspace(0.0, 10.0, CURVE_POINTS)
    fit = chart.add_fit_series(
        source_dataset_id="ds1",
        x_data=x,
        y_data=2.0 * x,
        label="Fit",
        style=FitStyle(
            confidence_lower=2.0 * x - 1.0,
            confidence_upper=2.0 * x + 1.0,
            **style_kwargs,
        ),
    )
    assert chart.data_series == [series, fit]
    return chart, fit


def _style_tab(chart: Chart, fit) -> StyleTab:
    style_tab = StyleTab(app_context=build_app_context())
    style_tab.show()
    style_tab.set_series_list(chart.data_series, selected_index=chart.data_series.index(fit))
    return style_tab


def test_fill_card_is_visible_for_a_fit_and_band_card_stays_visible():
    _qapp()
    chart, fit = _chart_with_fit()
    style_tab = _style_tab(chart, fit)

    assert style_tab.fill_card.isVisible() is True
    assert style_tab.band_card.isVisible() is True
    assert style_tab.marker_card.isVisible() is False


def test_load_fit_style_populates_the_fill_controls():
    _qapp()
    chart, fit = _chart_with_fit(
        color="#123456", fill_enabled=True, fill_color="#00ff00", fill_alpha=0.45,
        fill_orientation="horizontal", fill_base=1.5, fill_to_index=0,
        fill_range_enabled=True, fill_sections=[(4, 9), (20, -1)],
    )
    style_tab = _style_tab(chart, fit)

    assert style_tab.fill_enabled_toggle.isChecked() is True
    assert style_tab.fill_horizontal_toggle.isChecked() is True
    assert style_tab.fill_to_control.currentValue() == 0
    assert style_tab.fill_base_spin.value() == 1.5
    assert style_tab.fill_match_line_toggle.isChecked() is False
    assert style_tab.fill_color_row.currentColor() == "#00ff00"
    assert style_tab.fill_opacity_slider.value() == 0.45
    assert style_tab.fill_range_enabled_toggle.isChecked() is True
    # Sections are shown 1-based over the fit's own curve points; an open end
    # (-1) is shown as the last curve point.
    rows = [(start.value(), end.value()) for _, start, _, end, _ in style_tab.fill_section_rows]
    assert rows == [(5, 10), (21, CURVE_POINTS)]


def test_fill_to_options_list_the_other_series_but_not_the_fit_itself():
    _qapp()
    chart, fit = _chart_with_fit()
    style_tab = _style_tab(chart, fit)

    values = [style_tab.fill_to_control.itemData(i) for i in range(style_tab.fill_to_control.count())]
    assert values == [-1, 0]


def test_apply_fit_style_writes_the_fill_fields_and_keeps_the_band():
    _qapp()
    chart, fit = _chart_with_fit(band_fill_enabled=True, band_color="#ff0000", band_fill_alpha=0.6)
    style_tab = _style_tab(chart, fit)

    style_tab.fill_enabled_toggle.setChecked(checked=True)
    style_tab.fill_horizontal_toggle.setChecked(checked=True)
    style_tab.fill_to_control.setCurrentValue(0)
    style_tab.fill_match_line_toggle.setChecked(checked=False)
    style_tab.fill_color_row.setCurrentColor("#00ff00")
    style_tab.fill_opacity_slider.setValue(0.4)
    style_tab.apply_fit_style_to(fit)

    assert fit.style.fill_enabled is True
    assert fit.style.fill_orientation == "horizontal"
    assert fit.style.fill_to_index == 0
    assert fit.style.fill_color == "#00ff00"
    assert fit.style.fill_alpha == 0.4
    # The confidence band is a separate option: editing the fill leaves it as it was.
    assert fit.style.band_fill_enabled is True
    assert fit.style.band_color == "#ff0000"
    assert fit.style.band_fill_alpha == 0.6


def test_editing_the_band_leaves_the_fill_untouched():
    _qapp()
    chart, fit = _chart_with_fit(fill_enabled=True, fill_color="", fill_alpha=0.35, fill_base=2.0)
    style_tab = _style_tab(chart, fit)

    style_tab.band_opacity_slider.setValue(0.1)
    style_tab.apply_fit_style_to(fit)

    assert fit.style.band_fill_alpha == 0.1
    assert fit.style.fill_enabled is True
    assert fit.style.fill_color == ""
    assert fit.style.fill_alpha == 0.35
    assert fit.style.fill_base == 2.0


def test_fill_sections_address_the_fit_curve_points():
    """A section ending on the fit's last curve point is stored as open (-1),
    which needs the point count of the fit's precomputed curve, not of its
    source dataset (which this chart's project does not even have)."""
    _qapp()
    chart, fit = _chart_with_fit(fill_enabled=True)
    style_tab = _style_tab(chart, fit)

    style_tab.fill_range_enabled_toggle.setChecked(checked=True)
    style_tab.fill_add_section_button.click()
    _, start_spin, start_label, end_spin, _ = style_tab.fill_section_rows[0]
    # A new section spans the whole fit curve by default.
    assert end_spin.maximum() == CURVE_POINTS
    assert end_spin.value() == CURVE_POINTS
    start_spin.setValue(3)

    assert fit.style.fill_range_enabled is True
    assert fit.style.fill_sections == [(2, -1)]
    x = fit.precomputed_x_data[2]
    assert start_label.text() == f"x={x:.4g}, y={2.0 * x:.4g}"

