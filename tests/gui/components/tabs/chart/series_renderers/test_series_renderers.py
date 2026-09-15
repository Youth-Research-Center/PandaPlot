"""Tests for the 5 SeriesType render functions, using a bare matplotlib
Axes (no Qt/ChartEditorWidget needed -- these are pure matplotlib-drawing
functions taking already-resolved data and a typed style object).

Each test reproduces one existing chart_editor.py if/elif branch's exact
matplotlib call and asserts on the resulting artist -- pinning today's
rendering behavior before Task 3 deletes the original branches.
"""
import matplotlib

matplotlib.use("Agg")  # no display needed for these pure-drawing tests
import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.quiver import Quiver

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.series_renderers import (
    SERIES_RENDERERS,
    render_bar_series,
    render_hist_series,
    render_line_series,
    render_scatter_series,
    render_vector_series,
)
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style import (
    BarSeriesStyle,
    ColormapSeriesStyle,
    HeatmapSeriesStyle,
    HistSeriesStyle,
    LineSeriesStyle,
    ScatterSeriesStyle,
    VectorSeriesStyle,
)
from pandaplot.models.chart.series_type import SeriesType


def _series_data(**overrides):
    defaults = dict(x_data=[1, 2, 3], y_data=[4, 5, 6], x_err=None, y_err=None,
                     x_err_minus=None, y_err_minus=None, error=None,
                     u_data=None, v_data=None, magnitude_data=None)
    defaults.update(overrides)
    return SeriesData(**defaults)


def test_every_series_type_has_a_renderer():
    """Against the SeriesType enum, not a hardcoded list: a type with no
    entry here raises KeyError mid-render and blanks the whole chart."""
    assert set(SERIES_RENDERERS.keys()) == set(SeriesType)
    assert SERIES_RENDERERS[SeriesType.LINE] is render_line_series
    assert SERIES_RENDERERS[SeriesType.SCATTER] is render_scatter_series
    assert SERIES_RENDERERS[SeriesType.BAR] is render_bar_series
    assert SERIES_RENDERERS[SeriesType.HIST] is render_hist_series
    assert SERIES_RENDERERS[SeriesType.VECTOR] is render_vector_series


def test_render_line_series_draws_a_line_with_style_fields():
    fig, ax = plt.subplots()
    style = LineSeriesStyle(color="#ff0000", line_width=3.0, line_style="dashed",
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "My Line", 1.0, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    assert len(ax.lines) == 1
    line = ax.lines[0]
    assert line.get_color() == "#ff0000"
    assert line.get_linewidth() == 3.0
    assert line.get_label() == "My Line"
    plt.close(fig)


def test_render_line_series_draws_a_fill_when_enabled():
    fig, ax = plt.subplots()
    style = LineSeriesStyle(color="#00ff00", fill_enabled=True, fill_color="#0000ff",
                             fill_alpha=0.4, fill_orientation="vertical")
    calls = []

    def resolve_fill_baseline(query, horizontal):
        calls.append((list(query), horizontal))
        return 0.0

    render_line_series(ax, _series_data(), style, "L", 1.0, visible=True,
                        extra={"resolve_fill_baseline": resolve_fill_baseline})

    assert len(ax.collections) == 1  # fill_between produces a PolyCollection
    assert calls == [([1, 2, 3], False)]
    plt.close(fig)


def test_render_line_series_fill_alpha_halved_when_not_visible():
    fig, ax = plt.subplots()
    style = LineSeriesStyle(fill_enabled=True, fill_alpha=0.8)

    render_line_series(ax, _series_data(), style, "L", 0.3, visible=False,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    fill = ax.collections[0]
    assert fill.get_alpha() == 0.8 * 0.3
    plt.close(fig)


def test_render_line_series_annotates_points_when_show_value_labels_is_set():
    """#125: each point gets a text annotation of its own Y value."""
    fig, ax = plt.subplots()
    style = LineSeriesStyle(color="#ff0000", show_value_labels=True,
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "My Line", 1.0, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    assert [t.get_text() for t in ax.texts] == ["4", "5", "6"]
    plt.close(fig)


def test_render_line_series_draws_no_annotations_when_show_value_labels_is_unset():
    fig, ax = plt.subplots()
    style = LineSeriesStyle(color="#ff0000", marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "My Line", 1.0, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    assert len(ax.texts) == 0
    plt.close(fig)


def test_render_line_series_value_label_mode_x_shows_x_value():
    fig, ax = plt.subplots()
    style = LineSeriesStyle(show_value_labels=True, value_label_mode="x",
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "L", 1.0, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    assert [t.get_text() for t in ax.texts] == ["1", "2", "3"]
    plt.close(fig)


def test_render_line_series_value_label_mode_xy_shows_both():
    fig, ax = plt.subplots()
    style = LineSeriesStyle(show_value_labels=True, value_label_mode="xy",
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "L", 1.0, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    assert [t.get_text() for t in ax.texts] == ["1, 4", "2, 5", "3, 6"]
    plt.close(fig)


def test_render_line_series_draws_arrow_when_show_arrow_is_set():
    fig, ax = plt.subplots()
    style = LineSeriesStyle(show_value_labels=True, value_label_show_arrow=True,
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "L", 1.0, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    assert all(t.arrow_patch is not None for t in ax.texts)
    plt.close(fig)


def test_render_line_series_no_arrow_by_default():
    fig, ax = plt.subplots()
    style = LineSeriesStyle(show_value_labels=True,
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "L", 1.0, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    assert all(t.arrow_patch is None for t in ax.texts)
    plt.close(fig)


def test_render_line_series_uses_custom_offset():
    fig, ax = plt.subplots()
    style = LineSeriesStyle(show_value_labels=True, value_label_offset_x=3.0, value_label_offset_y=-4.0,
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "L", 1.0, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    assert all(t.xyann == (3.0, -4.0) for t in ax.texts)
    plt.close(fig)


def test_render_line_series_applies_text_color_and_background():
    fig, ax = plt.subplots()
    style = LineSeriesStyle(show_value_labels=True, value_label_text_color="#ff0000",
                             value_label_bg_color="#00ff00", value_label_bg_alpha=0.5,
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "L", 1.0, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    text = ax.texts[0]
    assert text.get_color() == "#ff0000"
    bbox_patch = text.get_bbox_patch()
    assert bbox_patch is not None
    assert bbox_patch.get_alpha() == 0.5
    plt.close(fig)


def test_render_line_series_no_background_box_when_bg_color_unset():
    fig, ax = plt.subplots()
    style = LineSeriesStyle(show_value_labels=True,
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "L", 1.0, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    assert ax.texts[0].get_bbox_patch() is None
    plt.close(fig)


def test_render_line_series_skips_nan_points_when_annotating():
    """NaN in either X or Y must skip that point's label entirely -- see
    annotate_point_labels' `pd.isna(x) or pd.isna(y): continue` guard."""
    fig, ax = plt.subplots()
    style = LineSeriesStyle(show_value_labels=True,
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(
        ax, _series_data(x_data=[1, np.nan, 3], y_data=[4, 5, np.nan]), style, "L", 1.0,
        visible=True, extra={"resolve_fill_baseline": lambda q, horizontal: 0.0},
    )

    assert [t.get_text() for t in ax.texts] == ["4"]
    plt.close(fig)


def test_render_scatter_series_skips_nan_points_when_annotating():
    fig, ax = plt.subplots()
    style = ScatterSeriesStyle(show_value_labels=True,
                                marker=MarkerStyle(marker_style="square", marker_size=3.0))

    render_scatter_series(
        ax, _series_data(x_data=[1, np.nan, 3], y_data=[4, 5, np.nan]), style, "S", 1.0,
        visible=True, extra={},
    )

    assert [t.get_text() for t in ax.texts] == ["4"]
    plt.close(fig)


def test_render_line_series_value_label_alpha_matches_renderer_alpha():
    """Value labels must fade with the series' own effective alpha (already
    computed by the caller as `series.alpha if series.visible else 0.3`,
    see chart_editor.py) rather than staying fully opaque -- a faded or
    hidden series shouldn't leave fully-opaque numbers behind."""
    fig, ax = plt.subplots()
    style = LineSeriesStyle(show_value_labels=True,
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "L", 0.4, visible=False,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    assert all(t.get_alpha() == 0.4 for t in ax.texts)
    plt.close(fig)


def test_render_line_series_value_label_arrow_and_background_fade_with_alpha():
    fig, ax = plt.subplots()
    style = LineSeriesStyle(show_value_labels=True, value_label_show_arrow=True,
                             value_label_bg_color="#00ff00", value_label_bg_alpha=0.5,
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "L", 0.4, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    text = ax.texts[0]
    assert text.arrow_patch.get_alpha() == 0.4
    assert text.get_bbox_patch().get_alpha() == pytest.approx(0.5 * 0.4)
    plt.close(fig)


def test_render_line_series_value_label_color_falls_back_to_series_color():
    """"Match series color" toggle writes value_label_text_color = "" --
    the label must then take on the series' own rendered color, not
    matplotlib's default text color (black)."""
    fig, ax = plt.subplots()
    style = LineSeriesStyle(color="#123456", show_value_labels=True,
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(), style, "L", 1.0, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    assert ax.texts[0].get_color() == "#123456"
    plt.close(fig)


def test_render_line_series_value_label_mode_x_handles_non_numeric_x():
    """X-axis data can be categorical/string (or datetime) rather than
    numeric -- unconditional f"{x:.3g}" raises TypeError for these, which
    previously blanked the whole chart. Must fall back to str(value)."""
    fig, ax = plt.subplots()
    style = LineSeriesStyle(show_value_labels=True, value_label_mode="x",
                             marker=MarkerStyle(marker_style="none", marker_size=1.0))

    render_line_series(ax, _series_data(x_data=["a", "b", "c"]), style, "L", 1.0, visible=True,
                        extra={"resolve_fill_baseline": lambda q, horizontal: 0.0})

    assert [t.get_text() for t in ax.texts] == ["a", "b", "c"]
    plt.close(fig)


def test_render_scatter_series_value_label_mode_x_shows_x_value():
    fig, ax = plt.subplots()
    style = ScatterSeriesStyle(show_value_labels=True, value_label_mode="x",
                                marker=MarkerStyle(marker_style="square", marker_size=3.0))

    render_scatter_series(ax, _series_data(), style, "S", 1.0, visible=True, extra={})

    assert [t.get_text() for t in ax.texts] == ["1", "2", "3"]
    plt.close(fig)


def test_render_scatter_series_applies_text_color_and_background():
    fig, ax = plt.subplots()
    style = ScatterSeriesStyle(show_value_labels=True, value_label_text_color="#123123",
                                value_label_bg_color="#456456", value_label_bg_alpha=0.25,
                                marker=MarkerStyle(marker_style="square", marker_size=3.0))

    render_scatter_series(ax, _series_data(), style, "S", 1.0, visible=True, extra={})

    text = ax.texts[0]
    assert text.get_color() == "#123123"
    bbox_patch = text.get_bbox_patch()
    assert bbox_patch is not None
    assert bbox_patch.get_alpha() == 0.25
    plt.close(fig)


def test_render_scatter_series_value_label_color_falls_back_to_series_color():
    fig, ax = plt.subplots()
    style = ScatterSeriesStyle(color="#654321", show_value_labels=True,
                                marker=MarkerStyle(marker_style="square", marker_size=3.0))

    render_scatter_series(ax, _series_data(), style, "S", 1.0, visible=True, extra={})

    assert ax.texts[0].get_color() == "#654321"
    plt.close(fig)


def test_render_scatter_series_value_label_color_falls_back_to_marker_color_not_base_color():
    """"Match series color" must match the point's actually-rendered fill --
    for Scatter that's `mfc` (marker.marker_color or style.color), not
    style.color directly. Scatter has no drawn line to make style.color the
    visible "series color" the way it is for Line, and the Style tab lets a
    user override the marker's own fill color independently of `color`
    (SeriesTypeSpec.supports_color=False for Scatter) -- so once a marker
    color override is set, the label must follow IT, not the unused base
    color underneath it."""
    fig, ax = plt.subplots()
    style = ScatterSeriesStyle(color="#654321", show_value_labels=True,
                                marker=MarkerStyle(marker_style="square", marker_size=3.0,
                                                    marker_color="#00ff00"))

    render_scatter_series(ax, _series_data(), style, "S", 1.0, visible=True, extra={})

    assert ax.texts[0].get_color() == "#00ff00"
    plt.close(fig)


def test_render_scatter_series_value_label_alpha_matches_renderer_alpha():
    fig, ax = plt.subplots()
    style = ScatterSeriesStyle(show_value_labels=True,
                                marker=MarkerStyle(marker_style="square", marker_size=3.0))

    render_scatter_series(ax, _series_data(), style, "S", 0.4, visible=False, extra={})

    assert all(t.get_alpha() == 0.4 for t in ax.texts)
    plt.close(fig)


def test_render_scatter_series_draws_a_scatter_collection():
    fig, ax = plt.subplots()
    style = ScatterSeriesStyle(color="#123456", marker=MarkerStyle(marker_style="square", marker_size=3.0))

    render_scatter_series(ax, _series_data(), style, "My Scatter", 1.0, visible=True, extra={})

    assert len(ax.collections) == 1
    assert ax.collections[0].get_label() == "My Scatter"
    plt.close(fig)


def test_render_scatter_series_annotates_points_when_show_value_labels_is_set():
    fig, ax = plt.subplots()
    style = ScatterSeriesStyle(color="#123456", show_value_labels=True,
                                marker=MarkerStyle(marker_style="square", marker_size=3.0))

    render_scatter_series(ax, _series_data(), style, "My Scatter", 1.0, visible=True, extra={})

    assert [t.get_text() for t in ax.texts] == ["4", "5", "6"]
    plt.close(fig)


def test_render_bar_series_draws_bars():
    fig, ax = plt.subplots()
    style = BarSeriesStyle(color="#654321")

    render_bar_series(ax, _series_data(), style, "My Bars", 1.0, visible=True, extra={})

    assert len(ax.patches) == 3  # one Rectangle per bar
    plt.close(fig)


def test_render_bar_series_adds_bar_labels_when_show_value_labels_is_set():
    """#125: matplotlib's bar_label() places one text per bar."""
    fig, ax = plt.subplots()
    style = BarSeriesStyle(color="#654321", show_value_labels=True)

    render_bar_series(ax, _series_data(), style, "My Bars", 1.0, visible=True, extra={})

    assert [t.get_text() for t in ax.texts] == ["4", "5", "6"]
    plt.close(fig)


def test_render_bar_series_draws_no_bar_labels_when_show_value_labels_is_unset():
    fig, ax = plt.subplots()
    style = BarSeriesStyle(color="#654321")

    render_bar_series(ax, _series_data(), style, "My Bars", 1.0, visible=True, extra={})

    assert len(ax.texts) == 0
    plt.close(fig)


def test_render_bar_series_applies_text_color_and_background():
    fig, ax = plt.subplots()
    style = BarSeriesStyle(color="#654321", show_value_labels=True,
                            value_label_text_color="#ff0000",
                            value_label_bg_color="#00ff00", value_label_bg_alpha=0.5)

    render_bar_series(ax, _series_data(), style, "My Bars", 1.0, visible=True, extra={})

    text = ax.texts[0]
    assert text.get_color() == "#ff0000"
    bbox_patch = text.get_bbox_patch()
    assert bbox_patch is not None
    assert bbox_patch.get_alpha() == 0.5
    plt.close(fig)


def test_render_bar_series_no_background_box_when_bg_color_unset():
    fig, ax = plt.subplots()
    style = BarSeriesStyle(color="#654321", show_value_labels=True)

    render_bar_series(ax, _series_data(), style, "My Bars", 1.0, visible=True, extra={})

    assert ax.texts[0].get_bbox_patch() is None
    plt.close(fig)


def test_render_bar_series_value_label_color_falls_back_to_series_color():
    fig, ax = plt.subplots()
    style = BarSeriesStyle(color="#abcdef", show_value_labels=True)

    render_bar_series(ax, _series_data(), style, "My Bars", 1.0, visible=True, extra={})

    assert ax.texts[0].get_color() == "#abcdef"
    plt.close(fig)


def test_render_bar_series_value_label_alpha_matches_renderer_alpha():
    """Bar labels must fade with the series' own effective alpha too (the
    same `alpha` already passed to axes.bar()) rather than staying fully
    opaque when the bars themselves are faded/hidden."""
    fig, ax = plt.subplots()
    style = BarSeriesStyle(color="#654321", show_value_labels=True)

    render_bar_series(ax, _series_data(), style, "My Bars", 0.4, visible=False, extra={})

    assert all(t.get_alpha() == 0.4 for t in ax.texts)
    plt.close(fig)


def test_render_bar_series_background_fades_with_alpha():
    fig, ax = plt.subplots()
    style = BarSeriesStyle(color="#654321", show_value_labels=True,
                            value_label_bg_color="#00ff00", value_label_bg_alpha=0.5)

    render_bar_series(ax, _series_data(), style, "My Bars", 0.4, visible=True, extra={})

    assert ax.texts[0].get_bbox_patch().get_alpha() == pytest.approx(0.5 * 0.4)
    plt.close(fig)


def test_render_hist_series_draws_a_histogram():
    fig, ax = plt.subplots()
    style = HistSeriesStyle(color="#ababab")

    render_hist_series(ax, _series_data(y_data=list(range(20))), style, "My Hist", 1.0, visible=True, extra={"bins": 5})

    assert len(ax.patches) == 5  # one Rectangle per bin
    plt.close(fig)


def test_render_vector_series_draws_a_quiver():
    fig, ax = plt.subplots()
    style = VectorSeriesStyle(vector_color="#00ff00")

    render_vector_series(ax, _series_data(u_data=[1.0, 0.5, -1.0], v_data=[0.5, -1.0, 0.5]),
                          style, "Field", 1.0, visible=True, extra={})

    quivers = [c for c in ax.collections if isinstance(c, Quiver)]
    assert len(quivers) == 1
    plt.close(fig)


def test_render_vector_series_with_magnitude_and_colormap():
    fig, ax = plt.subplots()
    style = VectorSeriesStyle(vector_colormap="plasma")

    render_vector_series(
        ax, _series_data(u_data=[1.0, 0.5, -1.0], v_data=[0.5, -1.0, 0.5],
                          magnitude_data=np.array([1.0, 1.1, 1.5])),
        style, "Field", 1.0, visible=True, extra={},
    )

    quivers = [c for c in ax.collections if isinstance(c, Quiver)]
    assert len(quivers) == 1
    assert quivers[0].get_cmap().name == "plasma"
    plt.close(fig)


def test_render_colormap_series_returns_scatter_mappable():
    from pandaplot.gui.components.tabs.chart.series_renderers.colormap import render_colormap_series

    fig, ax = plt.subplots()
    data = _series_data(z_data=[0.1, 0.5, 0.9])
    style = ColormapSeriesStyle()

    mappable = render_colormap_series(ax, data, style, "S", 1.0, visible=True,
                                       extra={"colormap": "viridis", "color_limits": (None, None)})

    assert mappable is not None
    assert len(ax.collections) == 1
    plt.close(fig)


def test_render_colormap_series_edge_matches_each_points_own_fill_by_default():
    """A Colormap series' fill color varies per point through the colormap
    (c=z_data) -- there's no single style.color an edge could "match" the
    way Line/Scatter's marker_edge_color falls back to style.color. The
    default (marker_edge_color == "", per MarkerStyle's default) instead
    resolves to matplotlib's "face" sentinel, which makes each point's edge
    exactly match ITS OWN fill color rather than a single fixed value."""
    from pandaplot.gui.components.tabs.chart.series_renderers.colormap import render_colormap_series

    fig, ax = plt.subplots()
    data = _series_data(z_data=[0.1, 0.5, 0.9])
    style = ColormapSeriesStyle()

    render_colormap_series(ax, data, style, "S", 1.0, visible=True,
                            extra={"colormap": "viridis", "color_limits": (None, None)})

    collection = ax.collections[0]
    fig.canvas.draw()  # "face" only resolves to concrete per-point RGBA at draw time
    assert collection.get_edgecolor().tolist() == collection.get_facecolor().tolist()
    assert len({tuple(c) for c in collection.get_facecolor()}) >= 2
    plt.close(fig)


def test_render_colormap_series_uses_an_explicit_edge_color_when_set():
    """Setting marker_edge_color to a literal value opts back out of the
    "match each point's fill" default -- render_colormap_series must pass
    it straight through, not silently ignore it."""
    from pandaplot.gui.components.tabs.chart.series_renderers.colormap import render_colormap_series

    fig, ax = plt.subplots()
    data = _series_data(z_data=[0.1, 0.5, 0.9])
    style = ColormapSeriesStyle(marker=MarkerStyle(marker_edge_color="#ff0000"))

    render_colormap_series(ax, data, style, "S", 1.0, visible=True,
                            extra={"colormap": "viridis", "color_limits": (None, None)})

    import matplotlib.colors as mcolors
    edge_colors = ax.collections[0].get_edgecolor()
    assert len(edge_colors) > 0
    assert tuple(edge_colors[0]) == mcolors.to_rgba("#ff0000")
    plt.close(fig)


def test_render_colormap_series_uses_the_shared_color_limits_not_its_own_data():
    """The colormap value range must come from extra["color_limits"] --
    computed by chart_editor.py from ALL Colormap/Heatmap series on the
    chart combined -- not derived from this series' own z_data, proving
    the shared-scale design actually reaches the renderer."""
    from pandaplot.gui.components.tabs.chart.series_renderers.colormap import render_colormap_series

    fig, ax = plt.subplots()
    data = _series_data(z_data=[0.1, 0.5, 0.9])
    style = ColormapSeriesStyle()

    mappable = render_colormap_series(ax, data, style, "S", 1.0, visible=True,
                                       extra={"colormap": "plasma", "color_limits": (-10.0, 10.0)})

    assert mappable.get_clim() == (-10.0, 10.0)
    assert mappable.get_cmap().name == "plasma"


def test_render_colormap_series_returns_none_for_non_numeric_z_data():
    """The Data tab's Z-column picker permits any column, including
    non-numeric ones -- passing raw strings straight to scatter(c=...)
    either raises or silently treats color-name strings as literal marker
    colors. Must return None (matching render_heatmap_series' contract)
    instead, so chart_editor.py surfaces a per-series error."""
    from pandaplot.gui.components.tabs.chart.series_renderers.colormap import render_colormap_series

    fig, ax = plt.subplots()
    data = _series_data(z_data=["a", "b", "c"])
    style = ColormapSeriesStyle()

    mappable = render_colormap_series(ax, data, style, "S", 1.0, visible=True,
                                       extra={"colormap": "viridis", "color_limits": (None, None)})

    assert mappable is None
    plt.close(fig)


def test_render_colormap_series_returns_none_for_empty_z_data():
    """An empty Z series must not produce a meaningless colorbar."""
    from pandaplot.gui.components.tabs.chart.series_renderers.colormap import render_colormap_series

    fig, ax = plt.subplots()
    data = _series_data(x_data=[], y_data=[], z_data=[])
    style = ColormapSeriesStyle()

    mappable = render_colormap_series(ax, data, style, "S", 1.0, visible=True,
                                       extra={"colormap": "viridis", "color_limits": (None, None)})

    assert mappable is None
    plt.close(fig)


def test_render_heatmap_series_returns_pcolormesh_mappable_for_grid_data():
    from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series

    fig, ax = plt.subplots()
    x = [0, 1, 0, 1]
    y = [0, 0, 1, 1]
    z = [1, 2, 3, 4]
    data = _series_data(x_data=x, y_data=y, z_data=z)
    style = HeatmapSeriesStyle(heatmap_gridding="grid")

    mappable = render_heatmap_series(ax, data, style, "S", 1.0, visible=True,
                                      extra={"colormap": "viridis", "color_limits": (None, None)})

    assert mappable is not None
    plt.close(fig)


def test_render_heatmap_series_uses_the_shared_colormap_and_limits():
    from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series

    fig, ax = plt.subplots()
    x = [0, 1, 0, 1]
    y = [0, 0, 1, 1]
    z = [1, 2, 3, 4]
    data = _series_data(x_data=x, y_data=y, z_data=z)
    style = HeatmapSeriesStyle(heatmap_gridding="grid")

    mappable = render_heatmap_series(ax, data, style, "S", 1.0, visible=True,
                                      extra={"colormap": "plasma", "color_limits": (0.0, 5.0)})

    assert mappable.get_cmap().name == "plasma"
    assert mappable.get_clim() == (0.0, 5.0)
    plt.close(fig)


def test_render_heatmap_series_returns_none_when_ungriddable():
    from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series

    fig, ax = plt.subplots()
    data = _series_data(x_data=[], y_data=[], z_data=[])
    style = HeatmapSeriesStyle()

    mappable = render_heatmap_series(ax, data, style, "S", 1.0, visible=True,
                                      extra={"colormap": "viridis", "color_limits": (None, None)})

    assert mappable is None
    plt.close(fig)


# --- Heatmap contour rendering (#191) ---

_HEATMAP_XYZ = dict(
    x_data=[0, 1, 2, 0, 1, 2, 0, 1, 2],
    y_data=[0, 0, 0, 1, 1, 1, 2, 2, 2],
    z_data=[1, 2, 3, 2, 3, 4, 3, 4, 5],
)


@pytest.mark.parametrize("gridding", ["grid", "binned", "interpolated", "triangulated"])
@pytest.mark.parametrize("render_mode", ["contour_lines", "contour_filled", "contour_filled_lines"])
def test_render_heatmap_series_contour_modes_produce_a_mappable(gridding, render_mode):
    from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series

    fig, ax = plt.subplots()
    data = _series_data(**_HEATMAP_XYZ)
    style = HeatmapSeriesStyle(heatmap_gridding=gridding, heatmap_resolution=6,
                                render_mode=render_mode, contour_levels=4)

    mappable = render_heatmap_series(ax, data, style, "S", 1.0, visible=True,
                                      extra={"colormap": "viridis", "color_limits": (None, None)})

    assert mappable is not None
    plt.close(fig)


def test_render_heatmap_series_contour_filled_uses_the_shared_colormap_and_limits():
    from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series

    fig, ax = plt.subplots()
    data = _series_data(**_HEATMAP_XYZ)
    style = HeatmapSeriesStyle(heatmap_gridding="grid", render_mode="contour_filled", contour_levels=4)

    mappable = render_heatmap_series(ax, data, style, "S", 1.0, visible=True,
                                      extra={"colormap": "plasma", "color_limits": (0.0, 5.0)})

    assert mappable.get_cmap().name == "plasma"
    assert mappable.get_clim() == (0.0, 5.0)
    plt.close(fig)


def test_render_heatmap_series_contour_lines_only_returns_the_line_contour_set():
    """With no fill requested, the line ContourSet itself is the mappable
    (still usable for a colorbar) -- there's no separate filled artist."""
    from matplotlib.contour import ContourSet

    from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series

    fig, ax = plt.subplots()
    data = _series_data(**_HEATMAP_XYZ)
    style = HeatmapSeriesStyle(heatmap_gridding="grid", render_mode="contour_lines", contour_levels=4)

    mappable = render_heatmap_series(ax, data, style, "S", 1.0, visible=True,
                                      extra={"colormap": "viridis", "color_limits": (None, None)})

    assert isinstance(mappable, ContourSet)
    plt.close(fig)


def test_render_heatmap_series_triangulated_mesh_returns_a_trimesh():
    from matplotlib.collections import TriMesh

    from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series

    fig, ax = plt.subplots()
    data = _series_data(**_HEATMAP_XYZ)
    style = HeatmapSeriesStyle(heatmap_gridding="triangulated", render_mode="mesh")

    mappable = render_heatmap_series(ax, data, style, "S", 1.0, visible=True,
                                      extra={"colormap": "viridis", "color_limits": (None, None)})

    assert isinstance(mappable, TriMesh)
    plt.close(fig)


def test_render_heatmap_series_triangulated_returns_none_for_too_few_points():
    from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series

    fig, ax = plt.subplots()
    data = _series_data(x_data=[0, 1], y_data=[0, 1], z_data=[1.0, 2.0])
    style = HeatmapSeriesStyle(heatmap_gridding="triangulated", render_mode="mesh")

    mappable = render_heatmap_series(ax, data, style, "S", 1.0, visible=True,
                                      extra={"colormap": "viridis", "color_limits": (None, None)})

    assert mappable is None
    plt.close(fig)


def test_render_heatmap_series_triangulated_returns_none_for_collinear_points():
    """A degenerate (all-collinear) triangulation makes matplotlib's
    qhull-backed Triangulation raise RuntimeError, not ValueError -- must
    still be treated as "nothing to render" rather than crashing the whole
    chart."""
    from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series

    fig, ax = plt.subplots()
    data = _series_data(x_data=[0, 1, 2, 3], y_data=[0, 0, 0, 0], z_data=[1.0, 2.0, 3.0, 4.0])
    style = HeatmapSeriesStyle(heatmap_gridding="triangulated", render_mode="mesh")

    mappable = render_heatmap_series(ax, data, style, "S", 1.0, visible=True,
                                      extra={"colormap": "viridis", "color_limits": (None, None)})

    assert mappable is None
    plt.close(fig)


def test_render_heatmap_series_contour_line_labels_does_not_raise():
    from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series

    fig, ax = plt.subplots()
    data = _series_data(**_HEATMAP_XYZ)
    style = HeatmapSeriesStyle(heatmap_gridding="grid", render_mode="contour_filled_lines",
                                contour_levels=4, contour_line_labels=True)

    mappable = render_heatmap_series(ax, data, style, "S", 1.0, visible=True,
                                      extra={"colormap": "viridis", "color_limits": (None, None)})

    assert mappable is not None
    plt.close(fig)


def test_render_heatmap_series_applies_contour_line_width():
    from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series

    fig, ax = plt.subplots()
    data = _series_data(**_HEATMAP_XYZ)
    style = HeatmapSeriesStyle(heatmap_gridding="grid", render_mode="contour_lines",
                                contour_levels=4, contour_line_width=4.5)

    mappable = render_heatmap_series(ax, data, style, "S", 1.0, visible=True,
                                      extra={"colormap": "viridis", "color_limits": (None, None)})

    assert all(lw == 4.5 for lw in mappable.get_linewidths())
    plt.close(fig)


def test_render_heatmap_series_applies_contour_line_width_triangulated():
    from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series

    fig, ax = plt.subplots()
    data = _series_data(**_HEATMAP_XYZ)
    style = HeatmapSeriesStyle(heatmap_gridding="triangulated", render_mode="contour_lines",
                                contour_levels=4, contour_line_width=2.5)

    mappable = render_heatmap_series(ax, data, style, "S", 1.0, visible=True,
                                      extra={"colormap": "viridis", "color_limits": (None, None)})

    assert all(lw == 2.5 for lw in mappable.get_linewidths())
    plt.close(fig)


def test_series_renderers_registry_includes_new_types():
    assert SeriesType.COLORMAP in SERIES_RENDERERS
    assert SeriesType.HEATMAP in SERIES_RENDERERS
