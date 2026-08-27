"""Regression test: the Style tab must expose a Confidence Band card
(enable toggle/color/opacity) for a selected fit-data entry, visible only
for "fit" targets, reading/writing `FitData.style.band_*` fields.
"""
import sys

import numpy as np
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_style import LineSeriesStyle
from pandaplot.models.project.items.chart import DataSeries, FitData


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _fit(**style_kwargs):
    return FitData(
        source_dataset_id="ds1",
        fit_type="linear",
        x_data=np.array([1.0, 2.0]),
        y_data=np.array([1.0, 2.0]),
        label="Fit",
        style=FitStyle(**style_kwargs),
    )


def _series():
    return DataSeries(
        dataset_id="ds1",
        x_column="x",
        y_column="y",
        label="Series",
        style=LineSeriesStyle(),
    )


def _fit_with_confidence(**style_kwargs):
    fit = _fit(**style_kwargs)
    fit.confidence_lower = np.array([0.5, 1.5])
    fit.confidence_upper = np.array([1.5, 2.5])
    return fit


def test_band_card_visible_only_for_fit_target_with_confidence_data():
    _qapp()
    app_context = build_app_context()
    style_tab = StyleTab(app_context=app_context)
    style_tab.show()

    # A fit with no confidence_lower/confidence_upper has nothing for the
    # band card's controls to act on (F4) -- it must stay hidden even when
    # selected.
    style_tab.set_selected("fit", _fit())
    assert style_tab.band_card.isVisible() is False

    style_tab.set_selected("fit", _fit_with_confidence())
    assert style_tab.band_card.isVisible() is True

    style_tab.set_selected("series", _series())
    assert style_tab.band_card.isVisible() is False


def test_load_fit_style_populates_band_controls_from_fitstyle():
    _qapp()
    app_context = build_app_context()
    style_tab = StyleTab(app_context=app_context)
    style_tab.show()

    fit = _fit_with_confidence(band_fill_enabled=True, band_fill_alpha=0.4, band_color="#112233")

    style_tab.load_fit_style(fit)

    assert style_tab.band_enabled_toggle.isChecked() is True
    assert style_tab.band_opacity_slider.value() == 0.4
    assert style_tab.band_color_row.currentColor() == "#112233"
    # A non-empty stored band_color is an explicit color, not "match line".
    assert style_tab.band_match_line_toggle.isChecked() is False
    # The swatch must load visible when showing an explicit color -- loading
    # it hidden here would visually contradict the unchecked toggle.
    assert style_tab.band_color_row.isVisible() is True


def test_load_fit_style_disables_the_band_swatch_when_matching_the_line():
    """Regression test: loading a fit whose band_color=="" (inherit/match
    line) must load the swatch hidden, matching the "Match line" toggle's
    own live-edit behavior (_on_band_match_line_toggled) -- a prior bug set
    this backwards, so an inherit-color fit loaded with the toggle checked
    but the swatch still editable until the user touched the toggle once."""
    _qapp()
    app_context = build_app_context()
    style_tab = StyleTab(app_context=app_context)
    style_tab.show()

    fit = _fit_with_confidence(band_color="")

    style_tab.load_fit_style(fit)

    assert style_tab.band_match_line_toggle.isChecked() is True
    assert style_tab.band_color_row.isVisible() is False


def test_apply_fit_style_to_writes_band_fields():
    _qapp()
    app_context = build_app_context()
    style_tab = StyleTab(app_context=app_context)

    fit = _fit_with_confidence()
    style_tab.load_fit_style(fit)
    style_tab.band_enabled_toggle.setChecked(checked=False)
    style_tab.band_opacity_slider.setValue(0.5)
    style_tab.band_match_line_toggle.setChecked(checked=False)
    style_tab.band_color_row.setCurrentColor("#445566")

    style_tab.apply_fit_style_to(fit)

    assert fit.style.band_fill_enabled is False
    assert fit.style.band_fill_alpha == 0.5
    assert fit.style.band_color == "#445566"


def test_apply_fit_style_to_preserves_inherit_sentinel_when_band_untouched():
    """F1 regression: a fit whose band_color is "" (inherit the line color)
    must keep that sentinel after an Apply that never touched the band
    controls -- previously apply_fit_style_to unconditionally wrote the
    swatch's stale prefilled value back into band_color, freezing a color
    the user never chose."""
    _qapp()
    app_context = build_app_context()
    style_tab = StyleTab(app_context=app_context)

    fit = _fit_with_confidence(color="#ff0000", band_color="")
    style_tab.load_fit_style(fit)
    assert style_tab.band_match_line_toggle.isChecked() is True

    # User only changes the line color, never touches the band card.
    style_tab.line_color_row.setCurrentColor("#0000ff")

    style_tab.apply_fit_style_to(fit)

    assert fit.style.band_color == ""


def test_apply_fit_style_to_preserves_explicit_band_color_when_untouched():
    """The explicit-color counterpart of the F1 regression above: a fit
    with a non-empty band_color must keep that exact color through an
    Apply that never touches the band controls."""
    _qapp()
    app_context = build_app_context()
    style_tab = StyleTab(app_context=app_context)

    fit = _fit_with_confidence(band_color="#abcdef")
    style_tab.load_fit_style(fit)
    assert style_tab.band_match_line_toggle.isChecked() is False
    assert style_tab.band_color_row.currentColor() == "#abcdef"

    style_tab.apply_fit_style_to(fit)

    assert fit.style.band_color == "#abcdef"
