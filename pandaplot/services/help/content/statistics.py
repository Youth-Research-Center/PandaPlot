"""Help topics for the statistical tests.

Titles, summaries, assumptions, explanations, formulas and examples are read
from ``STAT_TESTS`` when ``topics()`` is called, so the Help window and the
statistics panel's info dialog always show the same text. Only the numbered
steps, the parameter meanings, keywords and related links are written here.
"""

from pandaplot.analysis.stats_types import STAT_TESTS, InputMode, StatTestInfo, StatTestType
from pandaplot.services.help.content.panel_defaults import EXPECTED_MEAN, SIGNIFICANCE_ALPHA
from pandaplot.services.help.help_types import PANEL_TOPIC_STATISTICS, HelpCategory, HelpTopic

STAT_TEST_TOPIC_IDS: dict[StatTestType, str] = {
    StatTestType.ONE_SAMPLE_T: "stats.one_sample_t",
    StatTestType.INDEPENDENT_T: "stats.independent_t",
    StatTestType.PAIRED_T: "stats.paired_t",
    StatTestType.MANN_WHITNEY: "stats.mann_whitney",
    StatTestType.WILCOXON: "stats.wilcoxon",
    StatTestType.ONE_WAY_ANOVA: "stats.one_way_anova",
    StatTestType.KRUSKAL_WALLIS: "stats.kruskal_wallis",
    StatTestType.PEARSON: "stats.pearson",
    StatTestType.SPEARMAN: "stats.spearman",
    StatTestType.SHAPIRO: "stats.shapiro",
}

_KEYWORDS: dict[StatTestType, tuple[str, ...]] = {
    StatTestType.ONE_SAMPLE_T: ("t test", "t-test", "one sample", "single sample", "compare mean to value", "p-value", "hypothesis test"),
    StatTestType.INDEPENDENT_T: ("t test", "t-test", "two sample", "student", "welch", "compare two groups", "p-value", "hypothesis test"),
    StatTestType.PAIRED_T: ("t test", "t-test", "paired", "before and after", "repeated measures", "p-value", "hypothesis test"),
    StatTestType.MANN_WHITNEY: ("mann whitney", "wilcoxon rank-sum", "u test", "nonparametric", "non-parametric", "rank test", "p-value"),
    StatTestType.WILCOXON: ("wilcoxon", "signed rank", "paired", "nonparametric", "non-parametric", "rank test", "p-value"),
    StatTestType.ONE_WAY_ANOVA: ("anova", "analysis of variance", "f test", "compare several groups", "three groups", "p-value"),
    StatTestType.KRUSKAL_WALLIS: ("kruskal", "nonparametric anova", "non-parametric", "rank test", "compare several groups", "p-value"),
    StatTestType.PEARSON: ("correlation", "pearson r", "linear relationship", "r value", "association", "p-value"),
    StatTestType.SPEARMAN: ("correlation", "spearman rho", "rank correlation", "monotonic", "association", "p-value"),
    StatTestType.SHAPIRO: ("normality", "normal distribution", "shapiro wilk", "is my data normal", "gaussian", "p-value"),
}

# Tests whose alternatives are worded for the same kind of comparison.
_ALTERNATIVE_MEANINGS: dict[StatTestType, str] = {
    StatTestType.ONE_SAMPLE_T: (
        "Which kind of difference you are looking for. 'two-sided' (default) asks whether the mean differs from the expected mean in "
        "either direction; 'less' asks whether it is smaller; 'greater' asks whether it is larger."
    ),
    StatTestType.INDEPENDENT_T: (
        "'two-sided' (default) asks whether the two group means differ in either direction; 'less' asks whether Column A's mean is "
        "smaller than Column B's; 'greater' asks whether it is larger."
    ),
    StatTestType.PAIRED_T: (
        "'two-sided' (default) asks whether the paired measurements differ in either direction; 'less' asks whether Column A is "
        "smaller than Column B; 'greater' asks whether it is larger."
    ),
    StatTestType.MANN_WHITNEY: (
        "'two-sided' (default) asks whether the two groups differ in either direction; 'less' asks whether Column A's values tend to "
        "be smaller than Column B's; 'greater' asks whether they tend to be larger."
    ),
    StatTestType.WILCOXON: (
        "'two-sided' (default) asks whether the paired measurements differ in either direction; 'less' asks whether Column A tends "
        "to be smaller than Column B; 'greater' asks whether it tends to be larger."
    ),
    StatTestType.PEARSON: (
        "'two-sided' (default) asks whether there is any linear correlation; 'less' asks whether it is negative; 'greater' asks "
        "whether it is positive."
    ),
    StatTestType.SPEARMAN: (
        "'two-sided' (default) asks whether there is any rank correlation; 'less' asks whether it is negative; 'greater' asks "
        "whether it is positive."
    ),
}

_ALPHA_MEANING = (
    f"The significance level (default {SIGNIFICANCE_ALPHA.default}). The result's plain-language conclusion compares the p-value with this number: "
    "a p-value below it counts as significant. Smaller values (0.01) are stricter."
)
_POPMEAN_MEANING = f"The value you are testing the sample mean against (default {EXPECTED_MEAN.default})."
_EQUAL_VAR_MEANING = (
    "Checked by default, which runs the classic Student's t-test and assumes both groups spread out equally. Uncheck it to run "
    "Welch's t-test, which does not make that assumption."
)

_DATA_SELECTION: dict[InputMode, tuple[str, tuple[tuple[str, str], ...]]] = {
    InputMode.ONE: (
        "Under Data Selection, choose the Sample column.",
        (("Sample column", "The numeric column to test. Missing values are ignored."),),
    ),
    InputMode.TWO: (
        "Under Data Selection, choose Column A and Column B (two different numeric columns).",
        (
            ("Column A", "The first numeric column."),
            ("Column B", "The second numeric column. For paired and correlation tests, values in the same row belong together."),
        ),
    ),
    InputMode.MANY: (
        "Under Data Selection, select two or more group columns in the Groups list (Ctrl-click or Shift-click for several).",
        (("Groups", "The numeric columns to compare, one column per group."),),
    ),
}

_RELATED: dict[StatTestType, tuple[StatTestType, ...]] = {
    StatTestType.ONE_SAMPLE_T: (StatTestType.SHAPIRO, StatTestType.WILCOXON),
    StatTestType.INDEPENDENT_T: (StatTestType.MANN_WHITNEY, StatTestType.PAIRED_T, StatTestType.ONE_WAY_ANOVA, StatTestType.SHAPIRO),
    StatTestType.PAIRED_T: (StatTestType.WILCOXON, StatTestType.INDEPENDENT_T, StatTestType.SHAPIRO),
    StatTestType.MANN_WHITNEY: (StatTestType.INDEPENDENT_T, StatTestType.KRUSKAL_WALLIS),
    StatTestType.WILCOXON: (StatTestType.PAIRED_T, StatTestType.MANN_WHITNEY),
    StatTestType.ONE_WAY_ANOVA: (StatTestType.KRUSKAL_WALLIS, StatTestType.INDEPENDENT_T, StatTestType.SHAPIRO),
    StatTestType.KRUSKAL_WALLIS: (StatTestType.ONE_WAY_ANOVA, StatTestType.MANN_WHITNEY),
    StatTestType.PEARSON: (StatTestType.SPEARMAN, StatTestType.SHAPIRO),
    StatTestType.SPEARMAN: (StatTestType.PEARSON,),
    StatTestType.SHAPIRO: (StatTestType.ONE_SAMPLE_T, StatTestType.INDEPENDENT_T, StatTestType.PEARSON),
}


def _join_names(names: list[str]) -> str:
    """Join control names as "A", "A and B" or "A, B and C"."""
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _steps(info: StatTestInfo) -> tuple[str, ...]:
    """Build the how-to steps for a test from the controls its panel shows."""
    data_step, _ = _DATA_SELECTION[info.input_mode]
    steps = [
        "Open a dataset tab and open the Statistical Tests panel in the sidebar.",
        f"In Test, choose {info.label}.",
        data_step,
    ]
    options = ["Significance (α)"]
    if info.uses_popmean:
        options.append("Expected mean (μ₀)")
    if info.uses_alternative:
        options.append("Alternative")
    if info.uses_equal_var:
        options.append("the equal-variance checkbox")
    steps.append(f"Under Parameters, set {_join_names(options)}.")
    steps.append("Click Run to see the result in the Results box.")
    steps.append("Click Add to Project to save the result as a new dataset.")
    return tuple(steps)


def _parameters(test_type: StatTestType, info: StatTestInfo) -> tuple[tuple[str, str], ...]:
    """List the labels the panel shows for a test, with their meanings."""
    _, selection = _DATA_SELECTION[info.input_mode]
    parameters = list(selection)
    parameters.append(("Significance (α)", _ALPHA_MEANING))
    if info.uses_popmean:
        parameters.append(("Expected mean (μ₀)", _POPMEAN_MEANING))
    if info.uses_alternative:
        parameters.append(("Alternative", _ALTERNATIVE_MEANINGS[test_type]))
    if info.uses_equal_var:
        parameters.append(("Assume equal variance (uncheck for Welch)", _EQUAL_VAR_MEANING))
    return tuple(parameters)


def topics() -> list[HelpTopic]:
    """Return the help topics of this module.

    Returns:
        One topic per statistical test, in ``STAT_TESTS`` order.
    """
    result: list[HelpTopic] = []
    for test_type, info in STAT_TESTS.items():
        result.append(
            HelpTopic(
                id=STAT_TEST_TOPIC_IDS[test_type],
                title=info.label,
                category=HelpCategory.STATISTICS,
                summary=info.description,
                steps=_steps(info),
                explanation=info.explanation,
                assumptions=info.assumptions,
                parameters=_parameters(test_type, info),
                formula=info.formula,
                example=info.example,
                keywords=_KEYWORDS[test_type],
                related=(PANEL_TOPIC_STATISTICS, *(STAT_TEST_TOPIC_IDS[t] for t in _RELATED[test_type])),
            )
        )
    return result
