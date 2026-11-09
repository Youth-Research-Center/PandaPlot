"""Help topic for descriptive statistics.

The statistic labels are read from ``DESCRIPTIVE_STATS`` when ``topics()`` is
called; the one-line meanings are written here and keyed by the catalog's
stable statistic identifiers.
"""

from pandaplot.analysis.descriptive_types import DESCRIPTIVE_STATS
from pandaplot.analysis.preprocessing_types import PreprocessingMethod
from pandaplot.analysis.stats_types import StatTestType
from pandaplot.services.help.content.panel_defaults import DESCRIPTIVE_SIGNIFICANT_DIGITS
from pandaplot.services.help.content.preprocessing import PREPROCESSING_TOPIC_IDS
from pandaplot.services.help.content.statistics import STAT_TEST_TOPIC_IDS
from pandaplot.services.help.help_types import PANEL_TOPIC_DESCRIPTIVE, HelpCategory, HelpTopic

DESCRIPTIVE_OVERVIEW_TOPIC_ID = "descriptive.overview"

STAT_MEANINGS: dict[str, str] = {
    "count": "How many valid numbers the column holds. Empty cells and text are not counted.",
    "missing": "How many cells are empty or not numeric, so they were left out of every other statistic.",
    "mean": "The average: the sum of the values divided by how many there are. One extreme value can pull it a long way.",
    "std": (
        "The standard deviation, a typical distance of the values from the mean. Small means the values cluster tightly; "
        "large means they are spread out. It is the sample version (divides by n - 1) and needs at least two values."
    ),
    "variance": "The standard deviation squared, in squared units. The sample version (divides by n - 1); needs at least two values.",
    "sem": (
        "The standard error of the mean: the standard deviation divided by the square root of the count. It says how precisely the "
        "mean is known; more data makes it smaller."
    ),
    "cv": (
        "The coefficient of variation: the standard deviation divided by the mean, shown as a ratio and not as a percentage. "
        "It compares spread between columns with different units or sizes. It is not available when the mean is 0."
    ),
    "min": "The smallest value.",
    "q1": "The 25% quartile: a quarter of the values are below it.",
    "median": "The middle value (the 50% quartile): half of the values are below it. Unlike the mean, extreme values barely move it.",
    "q3": "The 75% quartile: three quarters of the values are below it.",
    "max": "The largest value.",
    "range": "The largest value minus the smallest value.",
    "iqr": "The interquartile range: the 75% quartile minus the 25% quartile. It is the spread of the middle half of the data.",
    "skewness": (
        "How lopsided the distribution is. Near 0 means roughly symmetric, positive means a longer tail towards large values, "
        "negative means a longer tail towards small values. Needs at least three values."
    ),
    "kurtosis": (
        "How heavy the tails are compared with a normal distribution (excess kurtosis). 0 matches a normal distribution, "
        "positive means more extreme values than normal, negative means fewer. Needs at least four values."
    ),
}


def topics() -> list[HelpTopic]:
    """Return the help topics of this module.

    Returns:
        A single overview topic that lists every statistic in ``DESCRIPTIVE_STATS``.
    """
    return [
        HelpTopic(
            id=DESCRIPTIVE_OVERVIEW_TOPIC_ID,
            title="Descriptive statistics",
            category=HelpCategory.DESCRIPTIVE,
            summary=(
                "Summarises a numeric column with a few numbers: how many values it has, where its centre is, how spread out it is "
                "and what shape it has."
            ),
            steps=(
                "Open a dataset tab and open the Descriptive Statistics panel in the sidebar.",
                "Under Columns, select one or more numeric columns (Ctrl-click or Shift-click for several), or click Select all.",
                f"Under Options, set Significant digits ({DESCRIPTIVE_SIGNIFICANT_DIGITS.default} by default) and decide whether to keep 'Also add a written report (note)' checked.",
                "Click Compute to preview the table in the Results box.",
                (
                    "Click Add to Project to save the table as a new dataset named 'Descriptive stats [<columns>]'. With the report "
                    "option checked, a note named 'Descriptive stats report [<columns>]' is added as well."
                ),
            ),
            explanation=(
                "Before running a test or fitting a curve, it helps to look at the data with a few summary numbers. The centre "
                "(mean, median) tells you where the values sit, the spread (standard deviation, IQR, range) tells you how much "
                "they vary, and the shape (skewness, kurtosis) tells you whether they are symmetric and how extreme the outliers are.\n\n"
                "The results table has one row per statistic and one column per variable, in the order listed under Parameters. "
                "Values that cannot be computed, for example the standard deviation of a single value, show as n/a.\n\n"
                "When the mean and the median are far apart, or the skewness is far from 0, the data is lopsided or has outliers. "
                "The median and IQR then describe it better than the mean and standard deviation."
            ),
            parameters=(
                ("Columns", "The numeric columns to summarise. Each column gets its own column in the results table."),
                (
                    "Significant digits",
                    (
                        f"How many significant digits the table shows ({DESCRIPTIVE_SIGNIFICANT_DIGITS.minimum} to "
                        f"{DESCRIPTIVE_SIGNIFICANT_DIGITS.maximum}, default {DESCRIPTIVE_SIGNIFICANT_DIGITS.default})."
                    ),
                ),
                ("Also add a written report (note)", "When checked (the default), Add to Project also adds a short plain-language report as a note."),
                *((label, STAT_MEANINGS[key]) for key, label in DESCRIPTIVE_STATS.items()),
            ),
            keywords=(
                "summary statistics", "describe", "mean", "average", "median", "standard deviation", "variance", "quartile",
                "percentile", "skew", "kurtosis", "spread", "outlier", "std", "sem", "cv", "iqr",
            ),
            related=(
                PANEL_TOPIC_DESCRIPTIVE,
                STAT_TEST_TOPIC_IDS[StatTestType.SHAPIRO],
                PREPROCESSING_TOPIC_IDS[PreprocessingMethod.STANDARDIZE],
                PREPROCESSING_TOPIC_IDS[PreprocessingMethod.ROBUST],
            ),
        )
    ]
