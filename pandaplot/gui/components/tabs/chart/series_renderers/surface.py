"""Renders a "surface" series: (x, y, z) gridded via
chart_3d.build_surface_mesh (mode = style.heatmap_gridding) and drawn with
plot_surface, colored through the chart's shared color scale.

Returns None (not a mappable) when there's no data to grid, so the caller
can skip the colorbar and surface a per-series error instead of drawing an
empty axes -- the same contract render_heatmap_series has.

`label` is deliberately not passed through: matplotlib's Legend has no
handler for the Poly3DCollection plot_surface returns, so a label would
only produce a warning on every render. chart_editor.py already skips the
legend entirely when nothing produced a real handle."""
from pandaplot.gui.components.tabs.chart.chart_3d import build_surface_mesh
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import SurfaceSeriesStyle


def render_surface_series(axes, series_data: SeriesData, style: SurfaceSeriesStyle,
                           label: str, alpha: float, *, visible: bool, extra: dict):
    vmin, vmax = extra["color_limits"]
    try:
        mesh_x, mesh_y, mesh_z = build_surface_mesh(
            series_data.x_data, series_data.y_data, series_data.z_data,
            style.heatmap_gridding, style.heatmap_resolution)
    except ValueError:
        return None
    return axes.plot_surface(
        mesh_x, mesh_y, mesh_z,
        cmap=extra["colormap"], vmin=vmin, vmax=vmax,
        edgecolor=style.edge_color or "none",
        linewidth=style.edge_width,
        shade=style.shade,
        alpha=alpha)
