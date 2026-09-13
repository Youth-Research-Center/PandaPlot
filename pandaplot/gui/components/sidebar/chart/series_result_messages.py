"""Shared preview/error message formatting for chart-series-scoped panels
(ChartAnalysisPanel, ChartTransformPanel) -- see #284."""

import pandas as pd


def format_series_result_preview(header_lines: list[str], df: pd.DataFrame) -> str:
    """Join `header_lines` with the shared "First rows:" + df.head(5) block
    used by ChartAnalysisPanel.preview() and ChartTransformPanel.preview().
    `header_lines` is the panel-specific lead lines, e.g.
    ["Operation: Derivative", "Series: Squared", "Result: 100 points -> dataset 'x'"].
    """
    lines = [*header_lines, "", "First rows:", df.head(5).to_string(index=False)]
    return "\n".join(lines)


def format_preview_error(exc: Exception) -> str:
    """Shared preview-exception message."""
    return f"❌ Preview error: {exc}"


def format_apply_failure(verb: str) -> str:
    """Shared apply-failure message, e.g. verb="analyze" or "transform"."""
    return f"❌ Could not {verb} the series. See the log for details."
