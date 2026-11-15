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


def test_render_fit_series_draws_nothing_on_a_3d_axes():
    fig = plt.figure()
    try:
        axes_3d = fig.add_subplot(projection="3d")
        series_data = SeriesData(
            x_data=np.array([1.0, 2.0]), y_data=np.array([1.0, 2.0]),
            x_err=None, y_err=None, x_err_minus=None, y_err_minus=None, error=None,
        )
        style = FitStyle(confidence_lower=np.array([0.5, 1.5]), confidence_upper=np.array([1.5, 2.5]))

        render_fit_series(axes_3d, series_data, style, "Fit", 1.0, visible=True, extra={})

        assert len(axes_3d.get_lines()) == 0
        assert len(axes_3d.collections) == 0
    finally:
        plt.close(fig)


# --- area fill (#431) ---

def _curve(n: int = 5) -> SeriesData:
    x = np.linspace(0.0, 4.0, n)
    return SeriesData(x_data=x, y_data=x ** 2 + 1.0, x_err=None, y_err=None, x_err_minus=None, y_err_minus=None, error=None)


def _baseline_extra(value: float = 0.0, calls: list | None = None) -> dict:
    def resolve(query, *, horizontal):
        if calls is not None:
            calls.append((np.asarray(query).copy(), horizontal))
        return value
    return {"resolve_fill_baseline": resolve}


def _vertices(collection) -> np.ndarray:
    return np.concatenate([path.vertices for path in collection.get_paths()])


def test_render_fit_series_draws_no_area_fill_by_default(axes):
    render_fit_series(axes, _curve(), FitStyle(), "Fit", 1.0, visible=True, extra=_baseline_extra())
    assert len(axes.collections) == 0


def test_render_fit_series_fills_to_the_resolved_baseline(axes):
    calls = []
    style = FitStyle(color="#123456", fill_enabled=True, fill_alpha=0.25, fill_base=-2.0)
    render_fit_series(axes, _curve(), style, "Fit", 1.0, visible=True, extra=_baseline_extra(-2.0, calls))

    assert len(axes.collections) == 1
    fill = axes.collections[0]
    assert fill.get_alpha() == pytest.approx(0.25)
    # "Match line": an empty fill_color takes the fit line's color.
    np.testing.assert_allclose(fill.get_facecolor()[0][:3], matplotlib.colors.to_rgb("#123456"))
    # The resolver is queried with the fit's own curve X for a vertical fill.
    assert len(calls) == 1
    np.testing.assert_array_equal(calls[0][0], _curve().x_data)
    assert calls[0][1] is False
    vertices = _vertices(fill)
    assert vertices[:, 1].min() == pytest.approx(-2.0)
    assert vertices[:, 1].max() == pytest.approx(17.0)


def test_render_fit_series_fills_between_the_fit_and_another_curve(axes):
    """fill_to_index resolves to another series' curve; the renderer must use
    the per-point array the resolver returns, not the constant fill_base."""
    other_curve = np.array([0.5, 1.0, 1.5, 2.0, 2.5])
    style = FitStyle(fill_enabled=True, fill_to_index=0, fill_base=-100.0)
    render_fit_series(axes, _curve(), style, "Fit", 1.0, visible=True,
                      extra={"resolve_fill_baseline": lambda _query, *, horizontal: other_curve})

    vertices = _vertices(axes.collections[0])
    assert vertices[:, 1].min() == pytest.approx(0.5)
    assert -100.0 not in vertices[:, 1]


def test_render_fit_series_horizontal_fill_sweeps_the_curve_y(axes):
    calls = []
    style = FitStyle(fill_enabled=True, fill_orientation="horizontal", fill_base=-1.0)
    render_fit_series(axes, _curve(), style, "Fit", 1.0, visible=True, extra=_baseline_extra(-1.0, calls))

    np.testing.assert_array_equal(calls[0][0], _curve().y_data)
    assert calls[0][1] is True
    vertices = _vertices(axes.collections[0])
    assert vertices[:, 0].min() == pytest.approx(-1.0)


def test_render_fit_series_limits_the_fill_to_selected_curve_points(axes):
    """Sections index the fit's precomputed curve points (inclusive, 0-based)."""
    style = FitStyle(fill_enabled=True, fill_range_enabled=True, fill_sections=[(1, 2)])
    render_fit_series(axes, _curve(), style, "Fit", 1.0, visible=True, extra=_baseline_extra())

    vertices = _vertices(axes.collections[0])
    assert vertices[:, 0].min() == pytest.approx(1.0)
    assert vertices[:, 0].max() == pytest.approx(2.0)


def test_render_fit_series_fades_the_area_fill_when_hidden(axes):
    style = FitStyle(fill_enabled=True, fill_alpha=0.5)
    render_fit_series(axes, _curve(), style, "Fit", 0.3, visible=False, extra=_baseline_extra())
    assert axes.collections[0].get_alpha() == pytest.approx(0.3 * 0.5)


def test_area_fill_and_confidence_band_keep_their_own_colors_and_layer_under_the_line(axes):
    from pandaplot.gui.components.tabs.chart.series_renderers.fit import CONFIDENCE_BAND_GID

    curve = _curve()
    style = FitStyle(
        color="#000000",
        fill_enabled=True, fill_color="#00ff00", fill_alpha=0.3,
        band_fill_enabled=True, band_color="#ff0000", band_fill_alpha=0.6,
        confidence_lower=curve.y_data - 1.0, confidence_upper=curve.y_data + 1.0,
    )
    render_fit_series(axes, curve, style, "Fit", 1.0, visible=True, extra=_baseline_extra())

    assert len(axes.collections) == 2
    area, band = axes.collections  # drawn in this order: fill first, band above it
    assert area.get_gid() != CONFIDENCE_BAND_GID
    assert band.get_gid() == CONFIDENCE_BAND_GID
    np.testing.assert_allclose(area.get_facecolor()[0][:3], matplotlib.colors.to_rgb("#00ff00"))
    assert area.get_alpha() == pytest.approx(0.3)
    np.testing.assert_allclose(band.get_facecolor()[0][:3], matplotlib.colors.to_rgb("#ff0000"))
    assert band.get_alpha() == pytest.approx(0.6)
    line = axes.get_lines()[0]
    assert area.get_zorder() <= band.get_zorder() < line.get_zorder()
    # Matplotlib draws equal-zorder artists in insertion order, so the band is painted over the fill.
    children = axes.get_children()
    assert children.index(area) < children.index(band)
