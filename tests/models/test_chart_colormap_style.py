from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style import ColormapSeriesStyle, HeatmapSeriesStyle


def test_colormap_series_style_defaults():
    style = ColormapSeriesStyle()
    assert style.z_column_id == ""
    assert style.z_column == ""
    assert isinstance(style.marker, MarkerStyle)
    assert not hasattr(style, "colormap")
    assert not hasattr(style, "colorbar_show")
    assert not hasattr(style, "colorbar_label")
    assert not hasattr(style, "color_scale_auto")
    assert not hasattr(style, "color_vmin")
    assert not hasattr(style, "color_vmax")


def test_heatmap_series_style_defaults():
    style = HeatmapSeriesStyle()
    assert style.z_column_id == ""
    assert style.heatmap_gridding == "grid"
    assert style.heatmap_resolution == 50
    assert style.render_mode == "mesh"
    assert style.contour_levels == 10
    assert style.contour_line_labels is False
    assert style.contour_line_width == 1.5
    assert not hasattr(style, "colormap")
    assert not hasattr(style, "colorbar_show")
    assert not hasattr(style, "colorbar_label")
    assert not hasattr(style, "color_scale_auto")
    assert not hasattr(style, "color_vmin")
    assert not hasattr(style, "color_vmax")


def test_series_types_registered():
    from pandaplot.models.chart.series_type import SeriesType
    assert SeriesType.COLORMAP == "colormap"
    assert SeriesType.HEATMAP == "heatmap"

    from pandaplot.models.chart.chart_type import ChartType
    assert ChartType.COLORMAP == "colormap"
    assert ChartType.HEATMAP == "heatmap"
