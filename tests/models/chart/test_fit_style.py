"""Tests for FitStyle after #304 moved FitData's metadata fields onto it."""
import dataclasses

import numpy as np

from pandaplot.models.chart.fit_style import FitStyle


def test_fit_style_has_moved_over_metadata_fields():
    field_names = {f.name for f in dataclasses.fields(FitStyle)}
    assert field_names == {
        "color", "line_style", "line_width",
        "band_fill_enabled", "band_fill_alpha", "band_color",
        "fit_type", "fit_params", "fit_stats",
        "confidence_lower", "confidence_upper",
        "confidence_lower_column_id", "confidence_upper_column_id",
        "is_manual",
    }
    assert "alpha" not in field_names


def test_fit_style_post_init_defaults():
    style = FitStyle()
    assert style.fit_params == {}
    assert style.fit_stats == {}
    assert style.confidence_lower is None
    assert style.confidence_upper is None
    assert style.is_manual is False


def test_series_style_from_dict_rebuilds_confidence_arrays():
    from pandaplot.models.chart.series_type import SeriesType
    from pandaplot.models.project.items.chart import _series_style_from_dict

    style_dict = {
        "color": "#ff0000", "line_style": "dashed", "line_width": 2.0,
        "band_fill_enabled": True, "band_fill_alpha": 0.2, "band_color": "",
        "fit_type": "linear", "fit_params": {"a": 1.0}, "fit_stats": {"r_squared": 0.9},
        "confidence_lower": [1.0, 2.0], "confidence_upper": [3.0, 4.0],
        "confidence_lower_column_id": "", "confidence_upper_column_id": "",
        "is_manual": False,
    }
    style = _series_style_from_dict(SeriesType.FIT, style_dict)
    assert isinstance(style, FitStyle)
    assert isinstance(style.confidence_lower, np.ndarray)
    np.testing.assert_array_equal(style.confidence_lower, [1.0, 2.0])
    np.testing.assert_array_equal(style.confidence_upper, [3.0, 4.0])
