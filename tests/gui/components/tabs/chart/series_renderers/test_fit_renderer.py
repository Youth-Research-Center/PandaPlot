"""Tests for render_fit_series (#304 -- replaces chart_editor.py's old
separate fit-rendering loop)."""
import matplotlib

matplotlib.use("Agg")  # no display needed for these pure-drawing tests
import matplotlib.pyplot as plt
import numpy as np
import pytest

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.series_renderers.fit import render_fit_series
from pandaplot.models.chart.fit_style import FitStyle


@pytest.fixture
def axes():
    fig, ax = plt.subplots()
    yield ax
    plt.close(fig)


def test_render_fit_series_draws_the_line(axes):
    series_data = SeriesData(
        x_data=np.array([1.0, 2.0, 3.0]), y_data=np.array([1.0, 4.0, 9.0]),
        x_err=None, y_err=None, x_err_minus=None, y_err_minus=None, error=None,
    )
    style = FitStyle(color="#123456", line_style="dashed", line_width=3.0)
    render_fit_series(axes, series_data, style, "My Fit", 1.0, visible=True, extra={})
    lines = axes.get_lines()
    assert len(lines) == 1
    assert lines[0].get_label() == "My Fit"
    assert lines[0].get_linewidth() == 3.0


def test_render_fit_series_draws_confidence_band_when_enabled(axes):
    series_data = SeriesData(
        x_data=np.array([1.0, 2.0]), y_data=np.array([1.0, 2.0]),
        x_err=None, y_err=None, x_err_minus=None, y_err_minus=None, error=None,
    )
    style = FitStyle(
        band_fill_enabled=True, band_fill_alpha=0.3,
        confidence_lower=np.array([0.5, 1.5]), confidence_upper=np.array([1.5, 2.5]),
    )
    render_fit_series(axes, series_data, style, "Fit", 1.0, visible=True, extra={})
    assert len(axes.collections) == 1  # fill_between produces a PolyCollection


def test_render_fit_series_fades_the_band_when_hidden(axes):
    """A hidden series renders at alpha=0.3*fill_alpha for a line's own
    fill (see render_line_series) -- the fit's confidence band must scale
    the same way, not stay fully opaque while the line itself fades."""
    series_data = SeriesData(
        x_data=np.array([1.0, 2.0]), y_data=np.array([1.0, 2.0]),
        x_err=None, y_err=None, x_err_minus=None, y_err_minus=None, error=None,
    )
    style = FitStyle(
        band_fill_enabled=True, band_fill_alpha=0.4,
        confidence_lower=np.array([0.5, 1.5]), confidence_upper=np.array([1.5, 2.5]),
    )
    render_fit_series(axes, series_data, style, "Fit", 0.3, visible=False, extra={})
    band = axes.collections[0]
    assert band.get_alpha() == pytest.approx(0.3 * 0.4)


def test_render_fit_series_skips_band_when_confidence_missing(axes):
    series_data = SeriesData(
        x_data=np.array([1.0]), y_data=np.array([1.0]),
        x_err=None, y_err=None, x_err_minus=None, y_err_minus=None, error=None,
    )
    style = FitStyle(band_fill_enabled=True)  # confidence_lower/upper stay None
    render_fit_series(axes, series_data, style, "Fit", 1.0, visible=True, extra={})
    assert len(axes.collections) == 0


def test_series_renderers_dispatch_includes_fit():
    from pandaplot.gui.components.tabs.chart.series_renderers import SERIES_RENDERERS
    from pandaplot.models.chart.series_type import SeriesType

    assert SERIES_RENDERERS[SeriesType.FIT] is render_fit_series
