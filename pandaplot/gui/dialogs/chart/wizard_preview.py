"""Live preview renderer for the chart wizard's Labels step, and the
sample-data preview its Type step shows before any data is picked.

Both previews go through the same per-series render functions the real
chart editor uses (`SERIES_RENDERERS`, keyed by SeriesType), rather than
each keeping its own if/elif chain of bare matplotlib calls: three such
chains had to be extended by hand for every new chart type, and they
drifted -- a preview drew a chart type differently from the chart the
wizard would actually create. Dispatching through the shared renderers
means the preview shows the real thing, with the same default styling
`build_series_style` gives a newly-created series, for every chart type
that exists.

What stays deliberately simplified is everything *around* the series:
a title/subtitle, axis labels, and on/off legend and grid -- exactly what
the wizard's Labels step exposes. Per-series color overrides, legend
position, grid color and the rest are still only ever set via Chart
Properties after Finish. This is not a second copy of
`ChartEditorWidget.update_chart()` and shouldn't grow into one.
"""
import numpy as np

from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas
from pandaplot.gui.components.tabs.chart.chart_editor import resolve_series_data
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.series_renderers import (
    SERIES_RENDERERS,
)
from pandaplot.gui.components.tabs.chart.series_renderers import (
    SERIES_RENDERERS_REPORTING_NO_DATA as _NO_DATA_MEANS_SKIP,
)
from pandaplot.gui.components.tabs.chart.series_renderers.box import BOX_POSITIONS_KEY
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style_builder import DEFAULT_SERIES_COLORS, build_series_style
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import DataSeries

_SAMPLE_X = [1, 2, 3, 4, 5]
_SAMPLE_Y = [2, 3, 1, 4, 3]
_SAMPLE_U = [1.0, 0.5, -1.0, 0.5, -0.5]
_SAMPLE_V = [0.5, -1.0, 0.5, 1.0, -0.5]

# A small regular lattice for the types that need a Z: enough points for a
# surface/wireframe to grid exactly (no binning) and for plot_trisurf to
# triangulate, and it doubles as the color ramp a Colormap/Heatmap sample
# needs. Z is a saddle so the 3-D samples show actual relief rather than a
# flat plane.
_SAMPLE_GRID_SIDE = 5
_SAMPLE_GRID_X, _SAMPLE_GRID_Y = (
    axis.ravel().tolist()
    for axis in np.meshgrid(np.arange(_SAMPLE_GRID_SIDE, dtype=float),
                            np.arange(_SAMPLE_GRID_SIDE, dtype=float))
)
_SAMPLE_GRID_Z = [
    (x - 2.0) ** 2 - (y - 2.0) ** 2
    for x, y in zip(_SAMPLE_GRID_X, _SAMPLE_GRID_Y, strict=True)
]
# Vector3D needs a Z column (the lattice above) AND U/V/W -- one per
# lattice point, unlike every other secondary-column type, which pairs
# U/V with the plain 5-point sample. A simple field radiating outward from
# the lattice's center reads as arrows rather than noise.
_SAMPLE_GRID_U = [0.3 * (x - 2.0) for x in _SAMPLE_GRID_X]
_SAMPLE_GRID_V = [0.3 * (y - 2.0) for y in _SAMPLE_GRID_Y]
_SAMPLE_GRID_W = [0.3] * len(_SAMPLE_GRID_X)
# The second sample layer a stacked type's preview draws on top of the
# first (matplotlib's second default cycle color, next to the first's blue).
_SAMPLE_STACK_COLOR = "#ff7f0e"
# Wedge names for a Pie sample, one per _SAMPLE_Y value, so the sample
# shows labeled wedges the way a configured label column would.
_SAMPLE_LABELS = ["A", "B", "C", "D", "E"]


def _preview_extra() -> dict:
    """The `extra` bag every render function is called with.

    A preview has no chart to read the real values off, so these are fixed
    defaults: matplotlib's own colormap, an auto color scale ((None, None)
    -- see resolve_color_limits), and a baseline resolver that's never
    actually called (only a fill-enabled Line series would, and a
    default-styled one never is). The bar stack and box_positions list are
    fresh per call, and shared by every series a single preview render draws
    with them, so a Stacked Bar preview stacks its series exactly as the real
    chart will, and several Box series sit side by side.
    """
    return {
        "bins": 10,
        "colormap": "viridis",
        "color_limits": (None, None),
        "resolve_fill_baseline": lambda _query, _horizontal: 0,
        "stack_bottoms": {},
        BOX_POSITIONS_KEY: [],
    }


def _sample_series_data(series_type: SeriesType) -> SeriesData:
    """Stand-in data for `series_type`, shaped by what its spec says it
    needs: the lattice for anything needing a Z column (a third axis, or a
    color ramp), U/V(/W) for a vector field, and the plain 5-point sample
    otherwise.

    Vector3D needs both at once (a Z column AND U/V/W) -- the only type
    that does -- so its U/V/W must be the lattice-sized arrays, not the
    plain 5-point ones every other secondary-column type (just Vector)
    pairs with."""
    spec = SERIES_TYPE_SPECS[series_type]
    on_lattice = spec.needs_z_column and spec.needs_secondary_columns
    if spec.needs_z_column:
        x_data, y_data, z_data = _SAMPLE_GRID_X, _SAMPLE_GRID_Y, _SAMPLE_GRID_Z
    else:
        x_data, y_data, z_data = _SAMPLE_X, _SAMPLE_Y, None
    u_data = (_SAMPLE_GRID_U if on_lattice else _SAMPLE_U) if spec.needs_secondary_columns else None
    v_data = (_SAMPLE_GRID_V if on_lattice else _SAMPLE_V) if spec.needs_secondary_columns else None
    w_data = _SAMPLE_GRID_W if (spec.needs_secondary_columns and spec.needs_w_column) else None
    return SeriesData(
        x_data=x_data, y_data=y_data,
        x_err=None, y_err=None, x_err_minus=None, y_err_minus=None, error=None,
        u_data=u_data, v_data=v_data, w_data=w_data,
        z_data=z_data,
        label_data=_SAMPLE_LABELS if spec.needs_label_column else None,
    )


def draw_chart_type_sample(canvas: ChartCanvas, chart_type: str) -> None:
    """Draw `chart_type`'s sample-data preview onto `canvas`, switching the
    canvas to the projection that type needs first.

    Shared by the wizard's Type step (which has no data at all yet) and the
    Labels step's fallback for when no configured series resolves, so the
    two steps can't show the same chart type differently.
    """
    canvas.set_projection(projection_3d=CHART_TYPE_SPECS[ChartType(chart_type)].is_3d)
    series_type = SeriesType(chart_type)
    style = build_series_style(series_type)
    extra = _preview_extra()
    SERIES_RENDERERS[series_type](
        canvas.axes, _sample_series_data(series_type), style,
        "", 1.0, visible=True, extra=extra)
    if SERIES_TYPE_SPECS[series_type].is_stacked:
        # One series alone looks exactly like a plain Bar sample -- stack a
        # second, differently-colored one on top so the preview shows what
        # actually sets this type apart.
        SERIES_RENDERERS[series_type](
            canvas.axes, _sample_series_data(series_type), build_series_style(series_type, color=_SAMPLE_STACK_COLOR),
            "", 1.0, visible=True, extra=extra)


def _series_label(project, config: dict) -> str:
    """Readable legend label for a series, e.g. "{dataset name}:{Y column name}".

    Mirrors `CreateChartFromWizardCommand._default_series_label` so the
    preview's legend matches what the actually-created chart shows. Degrades
    gracefully to the raw dataset id if the project or dataset can't resolve
    it -- this is only a preview, never worth crashing over.
    """
    dataset_id = config.get("dataset_id", "")
    if project is None:
        return dataset_id
    dataset = project.find_item(dataset_id)
    if not isinstance(dataset, Dataset):
        return dataset_id
    y_column_id = config.get("y_column_id", "")
    y_column_name = ""
    if y_column_id:
        y_column_name = dataset.column_name(y_column_id) or ""
    return f"{dataset.name}:{y_column_name}" if y_column_name else dataset.name


def render_wizard_preview(
    canvas: ChartCanvas, project, chart_type: str, series_configs: list[dict],
    title: str, subtitle: str, x_label: str, y_label: str,
    *, show_legend: bool, show_grid: bool,
) -> None:
    series_type = SeriesType(chart_type)
    spec = SERIES_TYPE_SPECS[series_type]
    canvas.set_projection(projection_3d=CHART_TYPE_SPECS[ChartType(chart_type)].is_3d)
    axes = canvas.axes
    axes.clear()

    extra = _preview_extra()
    any_plotted = False
    for index, config in enumerate(series_configs):
        style = build_series_style(
            series_type,
            # Same palette-by-index the created chart gets, so a stacked
            # preview shows its segments instead of one solid bar.
            color=DEFAULT_SERIES_COLORS[index % len(DEFAULT_SERIES_COLORS)],
            error_bars=ErrorBarConfig(
                x_error_column_id=config.get("x_error_column_id", ""),
                y_error_column_id=config.get("y_error_column_id", ""),
                x_error_minus_column_id=config.get("x_error_minus_column_id", ""),
                y_error_minus_column_id=config.get("y_error_minus_column_id", ""),
                error_symmetric=config.get("error_symmetric", True),
            ),
            u_column_id=config.get("u_column_id", ""),
            v_column_id=config.get("v_column_id", ""),
            w_column_id=config.get("w_column_id", ""),
            magnitude_column_id=config.get("magnitude_column_id", ""),
            z_column_id=config.get("z_column_id", ""),
            label_column_id=config.get("label_column_id", ""),
        )
        if spec.supports_gridding:
            style.heatmap_gridding = config.get("heatmap_gridding", "grid")
            style.heatmap_resolution = config.get("heatmap_resolution", 50)
        series = DataSeries(
            dataset_id=config["dataset_id"],
            x_column_id=config.get("x_column_id", ""),
            y_column_id=config.get("y_column_id", ""),
            series_type=series_type,
            style=style,
        )
        data = resolve_series_data(project, series, chart_type)
        if data.error is not None:
            continue
        # A renderer returning None may mean "nothing to draw" (see
        # SERIES_RENDERERS_REPORTING_NO_DATA) -- for those types it's this
        # series alone that failed, so skip it WITHOUT clearing
        # any_plotted, which would let the sample-data fallback below draw
        # on top of an earlier series that rendered fine (PR #190 review).
        rendered = SERIES_RENDERERS[series_type](
            axes, data, style, _series_label(project, config), 1.0, visible=True, extra=extra)
        if rendered is None and series_type in _NO_DATA_MEANS_SKIP:
            continue
        any_plotted = True

    if not any_plotted:
        # No resolvable series yet (wizard just opened, or the user hasn't
        # picked columns) -- fall back to the same sample data the Type
        # step's own preview uses, so the panel never renders empty axes.
        draw_chart_type_sample(canvas, chart_type)

    axes.set_title(f"{title}\n{subtitle}" if subtitle else title)
    has_axes = CHART_TYPE_SPECS[ChartType(chart_type)].has_axes
    if has_axes:
        axes.set_xlabel(x_label)
        axes.set_ylabel(y_label)
    else:
        # Same as the real editor: a Pie has no axes to label or grid.
        axes.set_axis_off()
    if show_legend and any_plotted:
        # Only when something actually carries a label. Several types pass
        # none at all -- matplotlib has no legend handler for the artists
        # pcolormesh/plot_surface/plot_wireframe/bar3d/plot_trisurf return
        # -- and legend() with no handles draws an empty framed box over
        # the plot and warns on every render. Mirrors the same check
        # chart_editor.py makes before building the real chart's legend.
        handles, labels = axes.get_legend_handles_labels()
        if handles:
            axes.legend(handles, labels)
    if has_axes:
        axes.grid(show_grid)
    canvas.draw()
