"""Tests for shared chart-series preview/error message formatting."""
import pandas as pd

from pandaplot.gui.components.sidebar.chart.series_result_messages import (
    format_apply_failure,
    format_preview_error,
    format_series_result_preview,
)


def test_format_series_result_preview_joins_headers_and_dataframe_head():
    df = pd.DataFrame({"x": [1, 2, 3], "y": [10, 20, 30]})

    text = format_series_result_preview(["Operation: Derivative", "Series: Squared"], df)

    assert text == (
        "Operation: Derivative\n"
        "Series: Squared\n"
        "\n"
        "First rows:\n"
        f"{df.head(5).to_string(index=False)}"
    )


def test_format_preview_error_includes_the_exception_message():
    assert format_preview_error(ValueError("bad input")) == "❌ Preview error: bad input"


def test_format_apply_failure_includes_the_verb():
    assert format_apply_failure("analyze") == (
        "❌ Could not analyze the series. See the log for details."
    )
    assert format_apply_failure("transform") == (
        "❌ Could not transform the series. See the log for details."
    )
