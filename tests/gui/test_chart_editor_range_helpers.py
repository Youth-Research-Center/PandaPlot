"""Unit tests for compute_axis_data_range(), the pure helper that computes
the (min, max) of all series data plotted against a given axis -- used to
populate the Axes tab's Range card in both Auto (disabled, for reference)
and the moment of switching into Manual (recompute-fresh)."""

from pandaplot.gui.components.tabs.chart.chart_editor import compute_axis_data_range
from pandaplot.models.project.items.chart import DataSeries, YAxis
from pandaplot.models.project.items.dataset import Dataset


class _FakeProject:
    def __init__(self, datasets):
        self._datasets = {d.id: d for d in datasets}

    def find_item(self, item_id):
        return self._datasets.get(item_id)


def _make_dataset(id_, x, y):
    import pandas as pd
    ds = Dataset(id=id_, name=id_)
    ds.data = pd.DataFrame({"x": x, "y": y})
    return ds


def test_computes_min_max_across_all_series_on_the_x_axis():
    ds = _make_dataset("ds1", x=[1, 5, 3], y=[10, 20, 30])
    project = _FakeProject([ds])
    series = [DataSeries(dataset_id="ds1", x_column="x", y_column="y")]
    assert compute_axis_data_range(project, series, "x") == (1.0, 5.0)


def test_computes_min_max_for_y_axis():
    ds = _make_dataset("ds1", x=[1, 2], y=[10, 20])
    project = _FakeProject([ds])
    series = [DataSeries(dataset_id="ds1", x_column="x", y_column="y")]
    assert compute_axis_data_range(project, series, "y") == (10.0, 20.0)


def test_y2_only_includes_secondary_axis_series():
    ds = _make_dataset("ds1", x=[1, 2], y=[10, 20])
    project = _FakeProject([ds])
    primary = DataSeries(dataset_id="ds1", x_column="x", y_column="y", y_axis=YAxis.PRIMARY)
    secondary = DataSeries(dataset_id="ds1", x_column="x", y_column="y", y_axis=YAxis.SECONDARY)
    secondary.y_column = "y"
    assert compute_axis_data_range(project, [primary, secondary], "y2") == (10.0, 20.0)
    assert compute_axis_data_range(project, [primary, secondary], "y") == (10.0, 20.0)


def test_returns_none_when_no_series_have_resolvable_data():
    project = _FakeProject([])
    series = [DataSeries(dataset_id="missing", x_column="x", y_column="y")]
    assert compute_axis_data_range(project, series, "x") is None


def test_returns_none_for_empty_series_list():
    project = _FakeProject([])
    assert compute_axis_data_range(project, [], "x") is None


def test_combines_min_max_across_multiple_series():
    ds1 = _make_dataset("ds1", x=[1, 2], y=[10, 20])
    ds2 = _make_dataset("ds2", x=[-5, 0], y=[100, 200])
    project = _FakeProject([ds1, ds2])
    series = [
        DataSeries(dataset_id="ds1", x_column="x", y_column="y"),
        DataSeries(dataset_id="ds2", x_column="x", y_column="y"),
    ]
    assert compute_axis_data_range(project, series, "x") == (-5.0, 2.0)


def test_positive_only_excludes_non_positive_values_from_range():
    """Log-scaled axes must ignore zero/negative data points -- matplotlib's
    own autoscale does the same when computing log-scale view limits."""
    ds = _make_dataset("ds1", x=[1, 2, 3], y=[-5, 10, 20])
    project = _FakeProject([ds])
    series = [DataSeries(dataset_id="ds1", x_column="x", y_column="y")]
    assert compute_axis_data_range(project, series, "y", positive_only=True) == (10.0, 20.0)
    assert compute_axis_data_range(project, series, "y") == (-5.0, 20.0)
    assert compute_axis_data_range(project, series, "y", positive_only=False) == (-5.0, 20.0)


def test_positive_only_series_with_all_non_positive_values_contributes_nothing():
    """If every value in the only series is <= 0 and positive_only=True,
    that series contributes no range at all -- matching the existing 'no
    resolvable data' contract of returning None."""
    ds = _make_dataset("ds1", x=[1, 2, 3], y=[-5, 0, -1])
    project = _FakeProject([ds])
    series = [DataSeries(dataset_id="ds1", x_column="x", y_column="y")]
    assert compute_axis_data_range(project, series, "y", positive_only=True) is None


def test_text_x_values_span_their_category_positions():
    """A text X column (e.g. 'Q1 2024') is drawn on matplotlib's categorical
    axis at positions 0..n-1, so the range is that span, not a float() crash."""
    ds = _make_dataset("ds1", x=["Q1 2024", "Q2 2024", "Q3 2024"], y=[10, 20, 30])
    project = _FakeProject([ds])
    series = [DataSeries(dataset_id="ds1", x_column="x", y_column="y")]
    assert compute_axis_data_range(project, series, "x") == (0.0, 2.0)
    assert compute_axis_data_range(project, series, "y") == (10.0, 30.0)


def test_text_x_categories_are_shared_across_series():
    """Series on one axis share one category list, in order of first
    appearance, so the range covers the union of their categories."""
    ds1 = _make_dataset("ds1", x=["a", "b"], y=[1, 2])
    ds2 = _make_dataset("ds2", x=["b", "c"], y=[3, 4])
    project = _FakeProject([ds1, ds2])
    series = [
        DataSeries(dataset_id="ds1", x_column="x", y_column="y"),
        DataSeries(dataset_id="ds2", x_column="x", y_column="y"),
    ]
    assert compute_axis_data_range(project, series, "x") == (0.0, 2.0)


def test_numeric_looking_text_x_values_are_categories_not_numbers():
    """Matplotlib draws the strings '1' and '2' as categories, never as the numbers 1 and 2."""
    ds = _make_dataset("ds1", x=["1", "2"], y=[10, 20])
    project = _FakeProject([ds])
    series = [DataSeries(dataset_id="ds1", x_column="x", y_column="y")]
    assert compute_axis_data_range(project, series, "x") == (0.0, 1.0)


def test_numeric_looking_text_labels_share_the_category_map_with_other_series():
    """['a', 'b'] then ['1', '2'] puts four categories on the axis, so the range ends at 3."""
    ds1 = _make_dataset("ds1", x=["a", "b"], y=[1, 2])
    ds2 = _make_dataset("ds2", x=["1", "2"], y=[3, 4])
    project = _FakeProject([ds1, ds2])
    series = [
        DataSeries(dataset_id="ds1", x_column="x", y_column="y"),
        DataSeries(dataset_id="ds2", x_column="x", y_column="y"),
    ]
    assert compute_axis_data_range(project, series, "x") == (0.0, 3.0)
