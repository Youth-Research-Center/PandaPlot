"""
Types and metadata for descriptive statistics.

This module defines the catalog of descriptive statistics that
:class:`~pandaplot.analysis.descriptive_engine.DescriptiveStatsEngine` computes
for one or more numeric columns, plus the result container used to surface the
summary in the application as data (a tidy table) and as a written report.
"""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

# Ordered catalog of the statistics reported for every column. The key is the
# stable identifier used in the results table; the value is the human-readable
# label shown to the user. Keeping this as a single ordered mapping means the
# engine, the results table, and the report all stay in the same order.
DESCRIPTIVE_STATS: dict[str, str] = {
    "count": "Count",
    "missing": "Missing",
    "mean": "Mean",
    "std": "Std. deviation",
    "variance": "Variance",
    "sem": "Std. error of mean",
    "cv": "Coeff. of variation",
    "min": "Minimum",
    "q1": "25% (Q1)",
    "median": "Median (Q2)",
    "q3": "75% (Q3)",
    "max": "Maximum",
    "range": "Range",
    "iqr": "IQR",
    "skewness": "Skewness",
    "kurtosis": "Kurtosis (excess)",
}


@dataclass
class DescriptiveStatsResult:
    """Descriptive statistics for one or more columns, ready to show as data.

    ``stats`` is a tidy table with one row per statistic (in
    :data:`DESCRIPTIVE_STATS` order) and one column per analysed variable, plus
    a leading ``Statistic`` column. This is what gets added to the project as a
    results dataset, and what :meth:`report` renders into prose.
    """

    source_columns: list[str]
    stats: pd.DataFrame
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dataframe(self) -> pd.DataFrame:
        """Return the tidy statistics table (Statistic + one column per variable)."""
        return self.stats

    def result_name(self) -> str:
        """Generate a default name for the results dataset."""
        cols = ", ".join(self.source_columns)
        return f"Descriptive stats [{cols}]"

    def report_name(self) -> str:
        """Generate a default name for the summary report note."""
        cols = ", ".join(self.source_columns)
        return f"Descriptive stats report [{cols}]"

    def report(self) -> str:
        """Render a human-readable Markdown report summarising the statistics.

        The report leads with a per-column table and follows with a short
        plain-language paragraph per column describing centre, spread and shape.
        """
        lines: list[str] = ["# Descriptive Statistics Report", ""]
        lines.append("Columns analysed: " + ", ".join(f"**{c}**" for c in self.source_columns))
        lines.append("")

        # Markdown table mirroring the tidy results DataFrame.
        headers = list(self.stats.columns)
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for _, row in self.stats.iterrows():
            lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
        lines.append("")

        # A short narrative per column.
        lines.append("## Summary")
        lines.append("")
        by_col = {row["Statistic"]: row for _, row in self.stats.iterrows()}
        for col in self.source_columns:
            lines.extend(self._column_narrative(col, by_col))
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def _column_narrative(self, col: str, by_col: dict[str, Any]) -> list[str]:
        """Build the prose bullet list for a single column."""

        def val(stat_key: str) -> str:
            row = by_col.get(DESCRIPTIVE_STATS[stat_key])
            return "n/a" if row is None else str(row[col])

        return [
            f"### {col}",
            f"- **{val('count')}** valid observations ({val('missing')} missing).",
            f"- Centre: mean **{val('mean')}**, median **{val('median')}**.",
            (f"- Spread: std. deviation **{val('std')}**, IQR **{val('iqr')}** "
            f"(range {val('min')} to {val('max')})."),
            f"- Shape: skewness **{val('skewness')}**, excess kurtosis **{val('kurtosis')}**.",
        ]
