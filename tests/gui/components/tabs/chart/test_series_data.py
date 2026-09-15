"""Tests for SeriesData.copy() -- must produce an independent snapshot
safe to read from a background thread while the source DataFrame is
mutated concurrently on the GUI thread."""
import pandas as pd

from pandaplot.gui.components.tabs.chart.series_data import SeriesData


def test_copy_produces_independent_arrays():
    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    data = SeriesData(x_data=df["x"], y_data=df["y"], x_err=None, y_err=None,
                       x_err_minus=None, y_err_minus=None, error=None)

    snapshot = data.copy()
    snapshot.x_data.iloc[0] = 999  # mutate the snapshot

    assert data.x_data.iloc[0] == 1  # original unaffected -- proves copy() didn't just alias
    assert snapshot.x_data.iloc[0] == 999  # the mutation was real


def test_copy_leaves_none_fields_as_none():
    data = SeriesData(x_data=None, y_data=None, x_err=None, y_err=None,
                       x_err_minus=None, y_err_minus=None, error="some error", z_label="z")
    snapshot = data.copy()
    assert snapshot.x_data is None
    assert snapshot.error == "some error"
    assert snapshot.z_label == "z"
