"""Tests for DataSeries.has_error_data, used by the Style tab to decide
whether the Error Bars card has anything to style."""
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style.line import LineSeriesStyle
from pandaplot.models.project.items.chart import DataSeries


def _series(**kwargs):
    """Build a line series with the given error-bar fields set on its
    nested style.error_bars (where error-bar config actually lives now
    -- see LineSeriesStyle), rather than as flat DataSeries kwargs."""
    style = LineSeriesStyle(error_bars=ErrorBarConfig(**kwargs)) if kwargs else None
    return DataSeries(dataset_id="ds1", x_column="x", y_column="y", style=style)


def test_no_error_columns_means_no_error_data():
    assert _series().has_error_data is False


def test_y_error_column_id_means_has_error_data():
    assert _series(y_error_column_id="col-id").has_error_data is True


def test_x_error_column_id_means_has_error_data():
    assert _series(x_error_column_id="col-id").has_error_data is True


def test_legacy_name_only_column_means_has_error_data():
    """Old projects loaded before stable column ids only populate the
    legacy name field, not the id field."""
    assert _series(y_error_column="err").has_error_data is True


def test_minus_only_column_means_has_error_data():
    """Regression test: a one-sided (asymmetric) uncertainty configured
    via ONLY the minus-side column, with no plus-side column set, must
    still report has_error_data -- build_error_array() treats a missing
    plus side as zero and still draws a real (one-sided) error bar, so
    hiding the Style tab's Error Bars card for this case would hide the
    only place to adjust color/cap size for bars that are on screen."""
    assert _series(y_error_minus_column_id="col-id", error_symmetric=False).has_error_data is True
    assert _series(x_error_minus_column_id="col-id", error_symmetric=False).has_error_data is True


def test_legacy_minus_only_name_means_has_error_data():
    assert _series(y_error_minus_column="err_minus", error_symmetric=False).has_error_data is True
