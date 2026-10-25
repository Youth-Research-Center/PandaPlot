"""Tests pinning resolve_series_data/compute_axis_data_range's per-type
column requirements to SERIES_TYPE_SPECS instead of hardcoded string
comparisons, and the compute_axis_data_range missing-chart_type-argument
bug fix."""
import pandas as pd
import pytest

from pandaplot.gui.components.tabs.chart.chart_editor import (
    compute_axis_data_range,
    resolve_series_data,
)
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import DataSeries
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project


@pytest.fixture
def project_with_series():
    project = Project(name="P")
    dataset = Dataset(id="ds-1", name="Data",
                       data=pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6], "z": [7, 8, 9]}))
    project.add_item(dataset)
    return project, dataset


def test_hist_does_not_require_x_column(project_with_series):
    project, dataset = project_with_series
    series = DataSeries(dataset_id="ds-1", x_column_id="", y_column_id=dataset.column_id("y"))

    data = resolve_series_data(project, series, "hist")

    assert data.error is None


def test_line_requires_resolvable_x_column_when_configured(project_with_series):
    project, dataset = project_with_series
    series = DataSeries(dataset_id="ds-1", x_column_id="", x_column="not_a_column",
                         y_column_id=dataset.column_id("y"))

    data = resolve_series_data(project, series, "line")

    assert data.error is not None


def test_compute_axis_data_range_passes_chart_type_through(project_with_series):
    """Regression test for the bug where compute_axis_data_range called
    resolve_series_data(project, series) with no chart_type, so a hist
    series' stale/unset x_column was always (incorrectly) required.
    compute_axis_data_range no longer takes a chart_type argument at all
    (Phase 4a): each series' own series_type governs this now, so the
    hist-ness is expressed on the series instead of passed in explicitly."""
    project, dataset = project_with_series
    series = DataSeries(dataset_id="ds-1", x_column_id="", y_column_id=dataset.column_id("y"),
                         series_type=SeriesType.HIST)

    result = compute_axis_data_range(project, [series], "x")

    # A hist series has no x-column data to range over (it plots only
    # y_data as a distribution) -- with chart_type correctly threaded
    # through, no x-range is produced, rather than erroring on a missing
    # x column that was never meant to be required.
    assert result is None


def test_resolve_series_data_derives_needs_x_column_from_series_type_when_chart_type_omitted(project_with_series):
    """A hist-typed series must not require an x-column even when no
    chart_type is passed -- the old behavior (chart_type=None -> always
    True) was the exact bug fixed in Phase 2; this pins the fix now
    deriving from series.series_type instead."""
    project, dataset = project_with_series
    series = DataSeries(dataset_id="ds-1", x_column_id="", y_column_id=dataset.column_id("y"),
                         series_type=SeriesType.HIST)

    data = resolve_series_data(project, series)

    assert data.error is None
    assert data.x_data is None


def test_resolve_series_data_line_series_still_requires_x_column_when_chart_type_omitted(project_with_series):
    project, dataset = project_with_series
    series = DataSeries(dataset_id="ds-1", x_column_id="", x_column="not_a_column",
                         y_column_id=dataset.column_id("y"), series_type=SeriesType.LINE)

    data = resolve_series_data(project, series)

    assert data.error is not None


def test_compute_axis_data_range_uses_each_series_own_type_not_a_shared_chart_type(project_with_series):
    """A chart containing a mix of a hist-typed series (no x-column) and a
    line-typed series (has an x-column) must compute the x-range from
    only the line series -- proving each series' OWN type governs its
    contribution, not one chart-wide type applied to the whole loop."""
    project, dataset = project_with_series
    hist_series = DataSeries(dataset_id="ds-1", x_column_id="", y_column_id=dataset.column_id("y"),
                              series_type=SeriesType.HIST)
    line_series = DataSeries(dataset_id="ds-1", x_column_id=dataset.column_id("x"),
                              y_column_id=dataset.column_id("y"), series_type=SeriesType.LINE)

    result = compute_axis_data_range(project, [hist_series, line_series], "x")

    assert result == (1.0, 3.0)  # from project_with_series' x column: [1, 2, 3]


def test_resolve_series_data_resolves_z_column_for_colormap(project_with_series):
    project, dataset = project_with_series
    from pandaplot.models.chart.series_style import ColormapSeriesStyle

    series = DataSeries(
        dataset_id=dataset.id, x_column_id=dataset.column_id("x"),
        y_column_id=dataset.column_id("y"), series_type=SeriesType.COLORMAP,
        style=ColormapSeriesStyle(z_column_id=dataset.column_id("z")),
    )
    data = resolve_series_data(project, series)
    assert data.error is None
    assert list(data.z_data) == list(dataset.data["z"])


def test_resolve_series_data_missing_z_column_errors(project_with_series):
    project, dataset = project_with_series
    from pandaplot.models.chart.series_style import HeatmapSeriesStyle

    series = DataSeries(
        dataset_id=dataset.id, x_column_id=dataset.column_id("x"),
        y_column_id=dataset.column_id("y"), series_type=SeriesType.HEATMAP,
        style=HeatmapSeriesStyle(z_column_id=""),
    )
    data = resolve_series_data(project, series)
    assert data.error is not None


def _density_range_fixture():
    import numpy as np
    import pandas as pd

    from pandaplot.models.chart.series_type import SeriesType
    from pandaplot.models.project.items import Dataset
    from pandaplot.models.project.items.chart import Chart
    from pandaplot.models.project.project import Project

    project = Project(name="p")
    values = np.random.default_rng(1).normal(10.0, 3.0, 100)
    dataset = Dataset(name="ds", data=pd.DataFrame({"v": values}))
    project.add_item(dataset)
    chart = Chart(name="c", chart_type="density")
    chart.add_data_series(dataset.id, y_column_id=dataset.column_id("v"), series_type=SeriesType.DENSITY)
    return project, chart, values


def test_axis_range_for_density_uses_the_rendered_kde_coordinates():
    from pandaplot.gui.components.tabs.chart.series_renderers.density import compute_density_curve

    project, chart, values = _density_range_fixture()
    grid, density = compute_density_curve(values, bandwidth=0.0)

    assert compute_axis_data_range(project, chart.data_series, "x") == (float(grid.min()), float(grid.max()))
    assert compute_axis_data_range(project, chart.data_series, "y") == (float(density.min()), float(density.max()))


def test_axis_range_includes_normalized_hist_overlay_on_a_density_chart():
    import numpy as np

    from pandaplot.models.chart.series_type import SeriesType

    project, chart, values = _density_range_fixture()
    dataset_id = chart.data_series[0].dataset_id
    chart.add_data_series(dataset_id, y_column_id=chart.data_series[0].y_column_id, series_type=SeriesType.HIST)
    heights, _ = np.histogram(values, bins=5, density=True)
    kde_max = compute_axis_data_range(project, chart.data_series[:1], "y")[1]

    low, high = compute_axis_data_range(project, chart.data_series, "y", hist_density_bins=5)

    assert low == 0.0
    assert high == max(kde_max, float(heights.max()))


def test_axis_range_for_a_filled_density_reaches_the_zero_baseline():
    project, chart, _values = _density_range_fixture()
    chart.data_series[0].style.fill_enabled = True

    assert compute_axis_data_range(project, chart.data_series, "y")[0] == 0.0
    assert compute_axis_data_range(project, chart.data_series, "y", positive_only=True)[0] > 0.0


def test_axis_range_for_a_constant_hist_overlay_uses_the_widened_bin_edges():
    import numpy as np
    import pandas as pd

    from pandaplot.models.chart.series_type import SeriesType
    from pandaplot.models.project.items import Dataset
    from pandaplot.models.project.items.chart import Chart
    from pandaplot.models.project.project import Project

    project = Project(name="p")
    dataset = Dataset(name="ds", data=pd.DataFrame({"v": [4.0] * 10}))
    project.add_item(dataset)
    chart = Chart(name="c", chart_type="density")
    chart.add_data_series(dataset.id, y_column_id=dataset.column_id("v"), series_type=SeriesType.HIST)
    _heights, edges = np.histogram([4.0] * 10, bins=5, density=True)

    low, high = compute_axis_data_range(project, chart.data_series, "x", hist_density_bins=5)

    assert (low, high) == (float(edges.min()), float(edges.max()))
    assert low < high
