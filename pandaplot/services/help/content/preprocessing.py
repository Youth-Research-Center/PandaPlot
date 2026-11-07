"""Help topics for the preprocessing methods.

Titles, summaries and formulas are read from ``PREPROCESSING_METHODS`` when
``topics()`` is called. The "when to use" explanations, steps, parameter
meanings, keywords and related links are written here.
"""

from pandaplot.analysis.preprocessing_types import PREPROCESSING_METHODS, PreprocessingInfo, PreprocessingMethod
from pandaplot.services.help.help_types import PANEL_TOPIC_PREPROCESSING, HelpCategory, HelpTopic

PREPROCESSING_TOPIC_IDS: dict[PreprocessingMethod, str] = {
    PreprocessingMethod.CENTER: "preprocessing.center",
    PreprocessingMethod.STANDARDIZE: "preprocessing.standardize",
    PreprocessingMethod.MINMAX: "preprocessing.minmax",
    PreprocessingMethod.ROBUST: "preprocessing.robust",
    PreprocessingMethod.MAXABS: "preprocessing.maxabs",
}

_EXPLANATIONS: dict[PreprocessingMethod, str] = {
    PreprocessingMethod.CENTER: (
        "Use this when only the position of the data matters, not its size: for example to compare how two columns vary around "
        "their own averages, or to remove a constant offset such as an instrument baseline.\n\n"
        "After centering, the mean of the column is zero. Values above the old mean become positive and values below it become "
        "negative. The units stay the same, so a spread of 3 mm is still 3 mm."
    ),
    PreprocessingMethod.STANDARDIZE: (
        "Use this to compare columns measured in different units or on very different scales, such as temperature in °C and "
        "pressure in kPa. Each value becomes the number of standard deviations it lies from the column's mean.\n\n"
        "A Z-score of 0 is exactly average, +1 is one standard deviation above average and -2 is two below. The new column has "
        "mean 0 and standard deviation 1. PandaPlot uses the population standard deviation (dividing by n). If every value in the "
        "column is the same, the standard deviation is 0 and the result is a column of zeros."
    ),
    PreprocessingMethod.MINMAX: (
        "Use this to squeeze a column into a fixed range, for example so that several series fit on the same 0 to 1 axis. "
        "The smallest value becomes the output minimum and the largest becomes the output maximum; everything else is placed "
        "proportionally between them.\n\n"
        "It keeps the shape of the data but is sensitive to outliers: one extreme value stretches the scale and squeezes all "
        "the other values together. If every value in the column is the same, all values are set to the output minimum."
    ),
    PreprocessingMethod.ROBUST: (
        "Use this when the column has outliers. The median and the interquartile range (IQR, the spread of the middle half of "
        "the data) barely move when a few extreme values are present, so the bulk of the data keeps a sensible scale.\n\n"
        "A value of 0 means the median, and a value of 1 means one IQR above the median. If the IQR is 0, the values are only "
        "centered on the median and not scaled."
    ),
    PreprocessingMethod.MAXABS: (
        "Use this when you want values between -1 and 1 without moving the data. Dividing by the largest absolute value "
        "keeps zeros at zero and keeps every value's sign.\n\n"
        "It suits data that is already centered or that has many zeros. If every value is 0, the column stays all zeros."
    ),
}

_KEYWORDS: dict[PreprocessingMethod, tuple[str, ...]] = {
    PreprocessingMethod.CENTER: ("mean removal", "subtract mean", "zero mean", "demean", "offset", "baseline", "normalize"),
    PreprocessingMethod.STANDARDIZE: ("z-score", "zscore", "z score", "standard score", "standardise", "normalize", "unit variance"),
    PreprocessingMethod.MINMAX: ("min-max", "min max", "normalize", "normalise", "rescale", "0 to 1", "feature range"),
    PreprocessingMethod.ROBUST: ("median", "iqr", "interquartile range", "outliers", "resistant", "normalize"),
    PreprocessingMethod.MAXABS: ("max-abs", "maximum absolute", "scale to -1 and 1", "normalize", "sparse"),
}

_RELATED: dict[PreprocessingMethod, tuple[PreprocessingMethod, ...]] = {
    PreprocessingMethod.CENTER: (PreprocessingMethod.STANDARDIZE,),
    PreprocessingMethod.STANDARDIZE: (PreprocessingMethod.CENTER, PreprocessingMethod.ROBUST, PreprocessingMethod.MINMAX),
    PreprocessingMethod.MINMAX: (PreprocessingMethod.MAXABS, PreprocessingMethod.STANDARDIZE),
    PreprocessingMethod.ROBUST: (PreprocessingMethod.STANDARDIZE, PreprocessingMethod.MINMAX),
    PreprocessingMethod.MAXABS: (PreprocessingMethod.MINMAX, PreprocessingMethod.CENTER),
}

_COLUMNS_MEANING = "The numeric columns to transform. Select one or more; each is transformed on its own. Missing values stay missing."
_REPLACE_MEANING = (
    "Unchecked by default, so each result is added as a new column next to the original. Checked, the original column is "
    "overwritten with the transformed values."
)
_OUTPUT_MIN_MEANING = "The value the column's smallest value is mapped to (default 0)."
_OUTPUT_MAX_MEANING = "The value the column's largest value is mapped to (default 1). It must be greater than Output min."


def _steps(info: PreprocessingInfo) -> tuple[str, ...]:
    """Build the how-to steps for a method from the controls its panel shows."""
    steps = [
        "Open a dataset tab and open the Preprocessing panel in the sidebar.",
        f"In Method, choose {info.label}.",
        "Under Columns, select the numeric columns to transform (Ctrl-click or Shift-click for several).",
    ]
    if info.uses_feature_range:
        steps.append(
            f"Under Parameters, set Output min ({info.default_range_min:g} by default) and Output max ({info.default_range_max:g} by default)."
        )
    steps.append(
        f"Under Result, leave 'Replace source columns in place' unchecked to add new columns named like <column>_{info.suffix}, "
        "or check it to overwrite the originals."
    )
    steps.append("Click Preview to see the fitted values and the first transformed values of the first selected column.")
    steps.append("Click Apply to write the transformed columns into the dataset. The change can be undone.")
    return tuple(steps)


def _parameters(info: PreprocessingInfo) -> tuple[tuple[str, str], ...]:
    """List the labels the panel shows for a method, with their meanings."""
    parameters = [("Columns", _COLUMNS_MEANING)]
    if info.uses_feature_range:
        parameters.append(("Output min", _OUTPUT_MIN_MEANING))
        parameters.append(("Output max", _OUTPUT_MAX_MEANING))
    parameters.append(("Replace source columns in place", _REPLACE_MEANING))
    return tuple(parameters)


def topics() -> list[HelpTopic]:
    """Return the help topics of this module.

    Returns:
        One topic per preprocessing method, in ``PREPROCESSING_METHODS`` order.
    """
    result: list[HelpTopic] = []
    for method, info in PREPROCESSING_METHODS.items():
        result.append(
            HelpTopic(
                id=PREPROCESSING_TOPIC_IDS[method],
                title=info.label,
                category=HelpCategory.PREPROCESSING,
                summary=info.description,
                steps=_steps(info),
                explanation=_EXPLANATIONS[method],
                parameters=_parameters(info),
                formula=info.formula,
                keywords=_KEYWORDS[method],
                related=(PANEL_TOPIC_PREPROCESSING, *(PREPROCESSING_TOPIC_IDS[m] for m in _RELATED[method])),
            )
        )
    return result
