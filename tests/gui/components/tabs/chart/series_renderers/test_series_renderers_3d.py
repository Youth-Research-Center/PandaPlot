"""Tests for the six 3-D SeriesType render functions, against a bare
mplot3d Axes (no Qt, no ChartEditorWidget -- these are pure drawing
functions over already-resolved data and a typed style object, exactly
like their 2-D siblings in test_series_renderers.py).
"""
import matplotlib

matplotlib.use("Agg")  # no display needed for these pure-drawing tests
import matplotlib.pyplot as plt
import pytest
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Path3DCollection, Poly3DCollection

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.series_renderers import (
    SERIES_RENDERERS,
    SERIES_RENDERERS_REPORTING_NO_DATA,
    render_bar3d_series,
    render_line3d_series,
    render_scatter3d_series,
    render_surface_series,
    render_trisurf_series,
    render_wireframe_series,
)
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style import (
    Bar3DSeriesStyle,
    Line3DSeriesStyle,
    Scatter3DSeriesStyle,
    SurfaceSeriesStyle,
    TrisurfSeriesStyle,
    WireframeSeriesStyle,
)
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS


def _axes3d():
    fig = plt.figure()
    return fig, fig.add_subplot(111, projection="3d")


def _lattice_data(side=3):
    """A `side` x `side` lattice -- griddable exactly, and enough points
    for plot_trisurf to triangulate."""
    x = [float(i) for i in range(side) for _ in range(side)]
    y = [float(j) for _ in range(side) for j in range(side)]
    z = [i + j for i, j in zip(x, y, strict=True)]
    return SeriesData(x_data=x, y_data=y, x_err=None, y_err=None,
                       x_err_minus=None, y_err_minus=None, error=None, z_data=z)


def _empty_data():
    return SeriesData(x_data=[], y_data=[], x_err=None, y_err=None,
                       x_err_minus=None, y_err_minus=None, error=None, z_data=[])


def _extra():
    return {"colormap": "viridis", "color_limits": (0.0, 4.0)}


def test_the_3d_renderers_are_registered_for_their_series_types():
    assert SERIES_RENDERERS[SeriesType.SCATTER3D] is render_scatter3d_series
    assert SERIES_RENDERERS[SeriesType.LINE3D] is render_line3d_series
    assert SERIES_RENDERERS[SeriesType.SURFACE] is render_surface_series
    assert SERIES_RENDERERS[SeriesType.WIREFRAME] is render_wireframe_series
    assert SERIES_RENDERERS[SeriesType.BAR3D] is render_bar3d_series
    assert SERIES_RENDERERS[SeriesType.TRISURF] is render_trisurf_series


def test_render_scatter3d_series_draws_a_3d_point_cloud_in_its_own_color():
    fig, axes = _axes3d()
    style = Scatter3DSeriesStyle(color="#ff0000",
                                  marker=MarkerStyle(marker_style="square", marker_size=4.0))

    render_scatter3d_series(axes, _lattice_data(), style, "pts", 1.0, visible=True, extra=_extra())

    scatters = [c for c in axes.collections if isinstance(c, Path3DCollection)]
    assert len(scatters) == 1
    plt.close(fig)


def test_render_line3d_series_draws_one_3d_line_with_its_style_fields():
    fig, axes = _axes3d()
    style = Line3DSeriesStyle(color="#00ff00", line_width=3.0, line_style="dashed",
                               marker=MarkerStyle(marker_style="none"))

    render_line3d_series(axes, _lattice_data(), style, "trace", 1.0, visible=True, extra=_extra())

    lines = axes.get_lines()
    assert len(lines) == 1
    assert lines[0].get_linewidth() == 3.0
    assert lines[0].get_label() == "trace"
    plt.close(fig)


def test_render_surface_series_returns_a_mappable_for_the_colorbar():
    """Surface takes its color from the chart's shared color scale, so it
    has to hand back the mappable chart_editor.py attaches the colorbar
    to (like the 2-D colormap/heatmap renderers do)."""
    fig, axes = _axes3d()

    mappable = render_surface_series(
        axes, _lattice_data(), SurfaceSeriesStyle(), "surf", 1.0, visible=True, extra=_extra())

    assert isinstance(mappable, Poly3DCollection)
    assert mappable.get_cmap().name == "viridis"
    plt.close(fig)


def test_render_wireframe_series_draws_a_line_mesh_in_one_flat_color():
    fig, axes = _axes3d()

    rendered = render_wireframe_series(
        axes, _lattice_data(), WireframeSeriesStyle(color="#123456", line_width=1.5),
        "mesh", 1.0, visible=True, extra=_extra())

    assert isinstance(rendered, Line3DCollection)
    plt.close(fig)


def test_render_bar3d_series_draws_one_box_collection():
    fig, axes = _axes3d()

    render_bar3d_series(axes, _lattice_data(), Bar3DSeriesStyle(), "bars", 1.0, visible=True, extra=_extra())

    assert len([c for c in axes.collections if isinstance(c, Poly3DCollection)]) == 1
    plt.close(fig)


class _RecordingAxes:
    """Captures the arguments a renderer passes to bar3d.

    bar3d's own output (a Poly3DCollection) only exposes its geometry after
    a projection pass, so asserting the *call* is both the direct statement
    of this renderer's contract and the stable one."""

    def __init__(self):
        self.bar3d_call = None

    def bar3d(self, x, y, z, dx, dy, dz, **kwargs):
        self.bar3d_call = (x, y, z, dx, dy, dz, kwargs)
        return "artist"


def test_render_bar3d_series_centers_each_box_on_its_own_data_point():
    """bar3d() takes each box's NEAR CORNER plus extents, so the renderer
    shifts the coordinates back by half a box -- otherwise every bar sits
    up and to the right of the point it represents (a 2-D bar chart
    centers on its x value, and this has to match)."""
    axes = _RecordingAxes()

    render_bar3d_series(axes, _lattice_data(), Bar3DSeriesStyle(bar_width=0.8, bar_depth=0.8),
                         "bars", 1.0, visible=True, extra=_extra())

    x, y, z, dx, dy, dz, _kwargs = axes.bar3d_call
    # Lattice spacing is 1.0, so a 0.8 fraction is a 0.8-wide box, and the
    # bar for x=0 starts at -0.4: it straddles its own coordinate.
    assert dx == pytest.approx(0.8)
    assert dy == pytest.approx(0.8)
    assert x[0] == pytest.approx(-0.4)
    assert y[0] == pytest.approx(-0.4)
    # Boxes rise from zero to the sample's z.
    assert list(z) == [0.0] * 9
    assert list(dz) == [0.0, 1.0, 2.0, 1.0, 2.0, 3.0, 2.0, 3.0, 4.0]


def test_render_bar3d_series_box_size_follows_the_data_spacing():
    """The same 0.8 fraction on data spaced 100 apart has to give an
    80-wide box, not an invisible 0.8-wide sliver."""
    axes = _RecordingAxes()
    wide = SeriesData(x_data=[0.0, 100.0, 200.0], y_data=[0.0, 100.0, 200.0],
                       x_err=None, y_err=None, x_err_minus=None, y_err_minus=None,
                       error=None, z_data=[1.0, 2.0, 3.0])

    render_bar3d_series(axes, wide, Bar3DSeriesStyle(bar_width=0.8, bar_depth=0.8),
                         "bars", 1.0, visible=True, extra=_extra())

    _x, _y, _z, dx, dy, _dz, _kwargs = axes.bar3d_call
    assert dx == pytest.approx(80.0)
    assert dy == pytest.approx(80.0)


def test_render_trisurf_series_returns_a_mappable_for_the_colorbar():
    fig, axes = _axes3d()

    mappable = render_trisurf_series(
        axes, _lattice_data(), TrisurfSeriesStyle(), "tri", 1.0, visible=True, extra=_extra())

    assert isinstance(mappable, Poly3DCollection)
    plt.close(fig)


def test_render_trisurf_series_returns_none_for_untriangulatable_points():
    """Three collinear points have no triangulation; matplotlib raises
    rather than drawing nothing, and that must not blank the whole chart."""
    fig, axes = _axes3d()
    collinear = SeriesData(x_data=[0.0, 1.0, 2.0], y_data=[0.0, 1.0, 2.0],
                            x_err=None, y_err=None, x_err_minus=None, y_err_minus=None,
                            error=None, z_data=[1.0, 2.0, 3.0])

    assert render_trisurf_series(
        axes, collinear, TrisurfSeriesStyle(), "tri", 1.0, visible=True, extra=_extra()) is None
    plt.close(fig)


@pytest.mark.parametrize("series_type", sorted(SERIES_RENDERERS_REPORTING_NO_DATA,
                                                key=lambda t: t.value))
def test_renderers_that_report_no_data_return_none_for_empty_input(series_type):
    """Every member of SERIES_RENDERERS_REPORTING_NO_DATA must honour that
    contract -- chart_editor.py turns the None into a per-series "no data"
    message, and a renderer that instead raised would blank the chart."""
    fig, axes = _axes3d() if SERIES_TYPE_SPECS[series_type].is_3d else plt.subplots()

    rendered = SERIES_RENDERERS[series_type](
        axes, _empty_data(), SERIES_TYPE_SPECS[series_type].style_cls(),
        "s", 1.0, visible=True, extra=_extra())

    assert rendered is None
    plt.close(fig)


def test_3d_renderers_accept_scattered_data_via_the_gridding_modes():
    """Surface/Wireframe are the gridding types: non-lattice points can't be
    pivoted exactly, and "binned" is what makes them renderable anyway."""
    fig, axes = _axes3d()
    scattered = SeriesData(
        x_data=[0.0, 0.4, 1.3, 2.2, 2.9, 1.1], y_data=[0.1, 1.2, 0.3, 2.4, 1.5, 2.6],
        x_err=None, y_err=None, x_err_minus=None, y_err_minus=None, error=None,
        z_data=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

    mappable = render_surface_series(
        axes, scattered, SurfaceSeriesStyle(heatmap_gridding="binned", heatmap_resolution=4),
        "surf", 1.0, visible=True, extra=_extra())

    assert isinstance(mappable, Poly3DCollection)
    plt.close(fig)
