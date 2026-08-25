"""Live preview renderer for the chart wizard's Labels step.

Deliberately self-contained rather than reusing
`ChartEditorWidget.update_chart()`: that method is ~500 lines tightly bound
to a persisted `Chart`, a live `ChartEditorWidget`, and its own zoom/pan/
toolbar state, so reusing it would mean a large refactor or embedding a
full editor in a tiny preview pane. Uses the same `resolve_series_data` as
the real renderer, but only styles what the Labels step exposes (title/
subtitle, axis labels, legend/grid on-off); everything else is still set
via Chart Properties after Finish, as today.
"""
from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas
from pandaplot.gui.components.tabs.chart.chart_editor import resolve_series_data
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import DataSeries

_SAMPLE_X = [1, 2, 3, 4, 5]
_SAMPLE_Y = [2, 3, 1, 4, 3]
_SAMPLE_U = [1.0, 0.5, -1.0, 0.5, -0.5]
_SAMPLE_V = [0.5, -1.0, 0.5, 1.0, -0.5]


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
    show_legend: bool, show_grid: bool,
) -> None:
    axes = canvas.axes
    axes.clear()

    series_type = SeriesType(chart_type)
    spec = SERIES_TYPE_SPECS[series_type]
    style_cls = spec.style_cls

    any_plotted = False
    for config in series_configs:
        if spec.supports_error_bars:
            style = style_cls(error_bars=ErrorBarConfig(
                x_error_column_id=config.get("x_error_column_id", ""),
                y_error_column_id=config.get("y_error_column_id", ""),
                x_error_minus_column_id=config.get("x_error_minus_column_id", ""),
                y_error_minus_column_id=config.get("y_error_minus_column_id", ""),
                error_symmetric=config.get("error_symmetric", True),
            ))
        elif series_type == SeriesType.VECTOR:
            style = style_cls(
                u_column_id=config.get("u_column_id", ""),
                v_column_id=config.get("v_column_id", ""),
                magnitude_column_id=config.get("magnitude_column_id", ""),
            )
        elif series_type in (SeriesType.COLORMAP, SeriesType.HEATMAP):
            style = style_cls(z_column_id=config.get("z_column_id", ""))
        else:
            style = style_cls()
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
        label = _series_label(project, config)
        if chart_type == "line":
            axes.plot(data.x_data, data.y_data, label=label)
        elif chart_type == "scatter":
            axes.scatter(data.x_data, data.y_data, label=label)
        elif chart_type == "bar":
            axes.bar(data.x_data, data.y_data, label=label)
        elif chart_type == "hist":
            axes.hist(data.y_data, bins=10, label=label)
        elif chart_type == "vector":
            axes.quiver(data.x_data, data.y_data, data.u_data, data.v_data, label=label)
        elif chart_type == "colormap":
            axes.scatter(data.x_data, data.y_data, c=data.z_data, cmap="viridis", label=label)
        elif chart_type == "heatmap":
            from pandaplot.gui.components.tabs.chart.chart_heatmap import build_heatmap_grid
            try:
                xs, ys, grid = build_heatmap_grid(
                    data.x_data, data.y_data, data.z_data,
                    config.get("heatmap_gridding", "grid"), config.get("heatmap_resolution", 50))
            except ValueError:
                # This series alone failed to grid -- must not erase an
                # earlier series' successful plot by resetting any_plotted
                # (PR #190 review). any_plotted is set once, below, only
                # for a series that actually drew something.
                continue
            axes.pcolormesh(xs, ys, grid, cmap="viridis", shading="nearest")
        any_plotted = True

    if not any_plotted:
        # No resolvable series yet (wizard just opened, or the user hasn't
        # picked columns) -- fall back to the same sample data the Type
        # step's own preview uses, so the panel never renders empty axes.
        if chart_type == "line":
            axes.plot(_SAMPLE_X, _SAMPLE_Y)
        elif chart_type == "scatter":
            axes.scatter(_SAMPLE_X, _SAMPLE_Y)
        elif chart_type == "bar":
            axes.bar(_SAMPLE_X, _SAMPLE_Y)
        elif chart_type == "hist":
            axes.hist(_SAMPLE_Y, bins=5)
        elif chart_type == "vector":
            axes.quiver(_SAMPLE_X, _SAMPLE_Y, _SAMPLE_U, _SAMPLE_V)
        elif chart_type == "colormap":
            axes.scatter(_SAMPLE_X, _SAMPLE_Y, c=_SAMPLE_Y, cmap="viridis")
        elif chart_type == "heatmap":
            import numpy as np
            grid = np.arange(16).reshape(4, 4)
            axes.pcolormesh(grid, cmap="viridis")

    axes.set_title(f"{title}\n{subtitle}" if subtitle else title)
    axes.set_xlabel(x_label)
    axes.set_ylabel(y_label)
    if show_legend and any_plotted:
        axes.legend()
    axes.grid(show_grid)
    canvas.draw()
