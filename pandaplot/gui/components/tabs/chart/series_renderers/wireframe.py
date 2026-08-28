"""Renders a "wireframe" series: the same grid a "surface" series builds
(see surface.py), drawn as an unfilled mesh in a single flat color.

`row_stride`/`column_stride` thin a dense grid down to a readable mesh.
Returns the Line3DCollection plot_wireframe draws, or None when there's
no data to grid (see SERIES_RENDERERS_REPORTING_NO_DATA) -- the artist is
returned only so a successful render is distinguishable from that failure,
never for a colorbar: a wireframe is drawn in one flat color, not through
the chart's color scale. Like plot_surface, matplotlib has no legend
handler for it, so no `label` is passed either."""
from pandaplot.gui.components.tabs.chart.chart_3d import build_surface_mesh
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.style_maps import LINESTYLE_MAP
from pandaplot.models.chart.series_style import WireframeSeriesStyle


def render_wireframe_series(axes, series_data: SeriesData, style: WireframeSeriesStyle,
                             label: str, alpha: float, *, visible: bool, extra: dict):
    try:
        mesh_x, mesh_y, mesh_z = build_surface_mesh(
            series_data.x_data, series_data.y_data, series_data.z_data,
            style.heatmap_gridding, style.heatmap_resolution)
    except ValueError:
        return None
    return axes.plot_wireframe(
        mesh_x, mesh_y, mesh_z,
        color=style.color,
        linewidth=style.line_width,
        linestyle=LINESTYLE_MAP.get(style.line_style, "-"),
        rstride=max(1, style.row_stride),
        cstride=max(1, style.column_stride),
        alpha=alpha)
