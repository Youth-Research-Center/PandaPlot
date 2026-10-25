"""
Types and metadata for guided statistical hypothesis testing.

This module defines the catalog of supported statistical tests together with
the metadata the guided UI needs to render inputs and help text, plus the
result container used to surface test output in the application as data.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd


class StatTestType(Enum):
    """Supported statistical tests."""

    ONE_SAMPLE_T = "one_sample_t"
    INDEPENDENT_T = "independent_t"
    PAIRED_T = "paired_t"
    MANN_WHITNEY = "mann_whitney"
    WILCOXON = "wilcoxon"
    ONE_WAY_ANOVA = "one_way_anova"
    KRUSKAL_WALLIS = "kruskal_wallis"
    PEARSON = "pearson"
    SPEARMAN = "spearman"
    SHAPIRO = "shapiro"


class InputMode(Enum):
    """How many columns a test consumes."""

    ONE = "one"  # A single sample column
    TWO = "two"  # Two sample columns (A and B)
    MANY = "many"  # Two or more group columns


class Alternative(Enum):
    """Alternative hypothesis direction."""

    TWO_SIDED = "two-sided"
    LESS = "less"
    GREATER = "greater"


@dataclass
class StatTestInfo:
    """Static metadata describing a statistical test for the guided UI."""

    test_type: StatTestType
    label: str
    input_mode: InputMode
    # Which optional parameters the test consumes.
    uses_alternative: bool = False
    uses_popmean: bool = False
    uses_equal_var: bool = False
    description: str = ""
    assumptions: str = ""
    # Learning-oriented content surfaced by the "ℹ️" info button.
    explanation: str = ""  # A fuller, plain-language explanation of the test.
    formula: str = ""  # The test statistic, written in simple notation with a legend.
    example: str = ""  # A concrete worked scenario and how to read the result.


# Catalog of tests grouped in a sensible order for the UI. This drives both the
# combo box and the dynamic input/parameter widgets in the statistics panel.
STAT_TESTS: dict[StatTestType, StatTestInfo] = {
    StatTestType.ONE_SAMPLE_T: StatTestInfo(
        test_type=StatTestType.ONE_SAMPLE_T,
        label="One-sample t-test",
        input_mode=InputMode.ONE,
        uses_alternative=True,
        uses_popmean=True,
        description="Tests whether the mean of a single sample differs from a known/expected value.",
        assumptions="Sample is approximately normally distributed; observations are independent.",
        explanation=(
            "Use this test when you have ONE group of measurements and want to know whether its average is "
            "different from a specific target number (μ₀) that you already expect or that a claim states.\n\n"
            "It works out how far your sample mean sits from the target, measured in standard errors. A large "
            "distance (big |t|) gives a small p-value, which is evidence the true mean really is different from the target."
        ),
        formula=(
            "t = (x̄ − μ₀) / (s / √n)\n\n"
            "x̄  = sample mean\n"
            "μ₀ = expected mean you are testing against\n"
            "s  = sample standard deviation\n"
            "n  = number of observations\n"
            "degrees of freedom = n − 1"
        ),
        example=(
            "A factory claims its bolts are 10 mm long on average. You measure 30 bolts and set μ₀ = 10.\n\n"
            "• p < 0.05  → the bolts' mean length is significantly different from 10 mm (the claim looks wrong).\n"
            "• p ≥ 0.05  → no evidence against the 10 mm claim."
        ),
    ),
    StatTestType.INDEPENDENT_T: StatTestInfo(
        test_type=StatTestType.INDEPENDENT_T,
        label="Independent (two-sample) t-test",
        input_mode=InputMode.TWO,
        uses_alternative=True,
        uses_equal_var=True,
        description="Compares the means of two independent groups.",
        assumptions="Each group is approximately normal; observations are independent. "
        "Uncheck 'equal variance' for Welch's t-test when variances differ.",
        explanation=(
            "Use this when you have TWO separate, unrelated groups and want to know whether their averages differ "
            "— for example a treatment group vs. a control group made up of different people.\n\n"
            "If the two groups have clearly different spreads (variances), uncheck 'equal variance' to use Welch's "
            "t-test, which is safer and usually the recommended default."
        ),
        formula=(
            "Student (equal variance):\n"
            "t = (x̄₁ − x̄₂) / (s_p · √(1/n₁ + 1/n₂))\n\n"
            "Welch (unequal variance):\n"
            "t = (x̄₁ − x̄₂) / √(s₁²/n₁ + s₂²/n₂)\n\n"
            "x̄₁, x̄₂ = group means\n"
            "s₁, s₂  = group standard deviations\n"
            "s_p     = pooled standard deviation\n"
            "n₁, n₂  = group sizes"
        ),
        example=(
            "Do students taught with Method A score differently from students taught with Method B? "
            "Put each class's scores in its own column.\n\n"
            "• p < 0.05  → the two teaching methods give significantly different average scores.\n"
            "• p ≥ 0.05  → no significant difference between the methods."
        ),
    ),
    StatTestType.PAIRED_T: StatTestInfo(
        test_type=StatTestType.PAIRED_T,
        label="Paired t-test",
        input_mode=InputMode.TWO,
        uses_alternative=True,
        description="Compares two related measurements (e.g. before/after) on the same subjects.",
        assumptions="Paired differences are approximately normal; pairs are independent.",
        explanation=(
            "Use this when the two columns are TWO measurements of the SAME subjects — such as 'before' and "
            "'after', or 'left hand' and 'right hand'. Each row is one subject.\n\n"
            "The test looks only at the difference within each pair, which removes person-to-person variation "
            "and makes it easier to detect a real change."
        ),
        formula=(
            "t = d̄ / (s_d / √n)\n\n"
            "dᵢ  = Aᵢ − Bᵢ  (difference for each pair)\n"
            "d̄   = mean of the differences\n"
            "s_d = standard deviation of the differences\n"
            "n   = number of pairs\n"
            "degrees of freedom = n − 1"
        ),
        example=(
            "Blood pressure is measured on 20 patients before and after a drug (before in column A, after in column B).\n\n"
            "• p < 0.05  → the drug produced a significant change in blood pressure.\n"
            "• p ≥ 0.05  → no significant before/after change."
        ),
    ),
    StatTestType.MANN_WHITNEY: StatTestInfo(
        test_type=StatTestType.MANN_WHITNEY,
        label="Mann-Whitney U (nonparametric)",
        input_mode=InputMode.TWO,
        uses_alternative=True,
        description="Nonparametric alternative to the independent t-test; compares distributions of two groups.",
        assumptions="Observations are independent. No normality assumption required.",
        explanation=(
            "The rank-based alternative to the independent t-test. Reach for it when your data is NOT normal, is "
            "skewed, has outliers, or is ordinal (e.g. ratings from 1–5).\n\n"
            "Instead of comparing means, it pools all values, ranks them from smallest to largest, and checks "
            "whether one group tends to hold the higher ranks."
        ),
        formula=(
            "U = n₁·n₂ + n₁(n₁ + 1)/2 − R₁\n\n"
            "R₁ = sum of the ranks of group 1 (after ranking both groups together)\n"
            "n₁, n₂ = group sizes\n"
            "The smaller of U₁ and U₂ is used as the statistic."
        ),
        example=(
            "Compare customer satisfaction ratings (1–5 stars) between two shops. Ratings are ordinal, so a "
            "t-test is not ideal.\n\n"
            "• p < 0.05  → one shop tends to receive higher ratings than the other.\n"
            "• p ≥ 0.05  → no significant difference in ratings."
        ),
    ),
    StatTestType.WILCOXON: StatTestInfo(
        test_type=StatTestType.WILCOXON,
        label="Wilcoxon signed-rank (nonparametric)",
        input_mode=InputMode.TWO,
        uses_alternative=True,
        description="Nonparametric alternative to the paired t-test for two related samples.",
        assumptions="Paired differences are symmetric. No normality assumption required.",
        explanation=(
            "The rank-based alternative to the paired t-test. Use it for before/after data on the same subjects "
            "when the differences are not normally distributed or contain outliers.\n\n"
            "It ranks the sizes of the paired differences (ignoring sign), then checks whether the positive and "
            "negative changes balance out or one direction dominates."
        ),
        formula=(
            "W = min(W⁺, W⁻)\n\n"
            "dᵢ = Aᵢ − Bᵢ  (pair differences, zeros dropped)\n"
            "Rank the |dᵢ| from smallest to largest\n"
            "W⁺ = sum of ranks where dᵢ > 0\n"
            "W⁻ = sum of ranks where dᵢ < 0"
        ),
        example=(
            "Ten judges rate a recipe before and after adding a spice. The rating differences look skewed.\n\n"
            "• p < 0.05  → the spice significantly changed the ratings.\n"
            "• p ≥ 0.05  → no significant change."
        ),
    ),
    StatTestType.ONE_WAY_ANOVA: StatTestInfo(
        test_type=StatTestType.ONE_WAY_ANOVA,
        label="One-way ANOVA",
        input_mode=InputMode.MANY,
        description="Tests whether the means of three or more groups are all equal.",
        assumptions="Groups are approximately normal with similar variances; observations are independent.",
        explanation=(
            "ANOVA (Analysis of Variance) extends the two-sample t-test to THREE OR MORE groups. It answers a "
            "single question: 'Are all the group means equal, or is at least one different?'\n\n"
            "It compares the variation BETWEEN the group means to the variation WITHIN the groups. If the between-"
            "group variation is large relative to the within-group noise, the means are unlikely to all be equal. "
            "Note: a significant result tells you some group differs, but not which one — that needs a follow-up test."
        ),
        formula=(
            "F = MS_between / MS_within\n\n"
            "MS_between = SS_between / (k − 1)\n"
            "MS_within  = SS_within  / (N − k)\n\n"
            "k = number of groups\n"
            "N = total number of observations\n"
            "SS = sum of squares (between-group vs. within-group)"
        ),
        example=(
            "Three fertilizers (A, B, C) are each applied to several plots; put each fertilizer's yields in its own column.\n\n"
            "• p < 0.05  → at least one fertilizer gives a different average yield.\n"
            "• p ≥ 0.05  → no significant difference among the fertilizers."
        ),
    ),
    StatTestType.KRUSKAL_WALLIS: StatTestInfo(
        test_type=StatTestType.KRUSKAL_WALLIS,
        label="Kruskal-Wallis (nonparametric)",
        input_mode=InputMode.MANY,
        description="Nonparametric alternative to one-way ANOVA; compares distributions across groups.",
        assumptions="Observations are independent. No normality assumption required.",
        explanation=(
            "The rank-based alternative to one-way ANOVA for THREE OR MORE groups. Use it when the data is not "
            "normal, is skewed, or is ordinal.\n\n"
            "All values are ranked together and the test checks whether some groups systematically hold higher or "
            "lower ranks than others."
        ),
        formula=(
            "H = [ 12 / (N(N + 1)) ] · Σ (Rᵢ² / nᵢ) − 3(N + 1)\n\n"
            "N  = total number of observations\n"
            "nᵢ = size of group i\n"
            "Rᵢ = sum of ranks in group i\n"
            "degrees of freedom = k − 1  (k = number of groups)"
        ),
        example=(
            "Compare pain scores (0–10) across three treatments. Scores are ordinal and skewed, so ANOVA is not ideal.\n\n"
            "• p < 0.05  → at least one treatment's pain scores differ from the others.\n"
            "• p ≥ 0.05  → no significant difference among treatments."
        ),
    ),
    StatTestType.PEARSON: StatTestInfo(
        test_type=StatTestType.PEARSON,
        label="Pearson correlation",
        input_mode=InputMode.TWO,
        uses_alternative=True,
        description="Measures the strength of a linear relationship between two variables.",
        assumptions="Relationship is linear; both variables are approximately normal.",
        explanation=(
            "Measures how strongly two numeric variables move together in a STRAIGHT-LINE (linear) way. The result "
            "r ranges from −1 to +1:\n\n"
            "• r near +1 → as one goes up, the other goes up.\n"
            "• r near −1 → as one goes up, the other goes down.\n"
            "• r near  0 → no linear relationship.\n\n"
            "Remember: correlation is not causation, and r only captures straight-line patterns."
        ),
        formula=(
            "r = Σ (xᵢ − x̄)(yᵢ − ȳ) / √[ Σ(xᵢ − x̄)² · Σ(yᵢ − ȳ)² ]\n\n"
            "xᵢ, yᵢ = paired values\n"
            "x̄, ȳ   = means of X and Y\n"
            "r      = correlation coefficient (−1 to +1)"
        ),
        example=(
            "Is height related to weight? Put height in column X and weight in column Y.\n\n"
            "• r = 0.8, p < 0.05 → a strong positive linear relationship.\n"
            "• p ≥ 0.05          → no significant linear relationship."
        ),
    ),
    StatTestType.SPEARMAN: StatTestInfo(
        test_type=StatTestType.SPEARMAN,
        label="Spearman correlation (rank)",
        input_mode=InputMode.TWO,
        uses_alternative=True,
        description="Measures the strength of a monotonic (rank-based) relationship between two variables.",
        assumptions="Relationship is monotonic. No normality assumption required.",
        explanation=(
            "Like Pearson, but based on RANKS instead of raw values. It measures whether two variables move in the "
            "same direction consistently (a monotonic relationship), even if the trend is curved rather than a "
            "straight line.\n\n"
            "It is more robust to outliers and works with ordinal data, which makes it a good first choice when the "
            "relationship looks curved or the data is not normal."
        ),
        formula=(
            "ρ = 1 − [ 6 · Σ dᵢ² ] / [ n(n² − 1) ]\n\n"
            "dᵢ = difference between the ranks of xᵢ and yᵢ\n"
            "n  = number of pairs\n"
            "ρ  = rank correlation (−1 to +1)"
        ),
        example=(
            "Does exam rank relate to hours studied when the trend curves off? Spearman captures the consistent "
            "'more study → better rank' pattern.\n\n"
            "• ρ = 0.7, p < 0.05 → a strong monotonic relationship.\n"
            "• p ≥ 0.05          → no significant monotonic relationship."
        ),
    ),
    StatTestType.SHAPIRO: StatTestInfo(
        test_type=StatTestType.SHAPIRO,
        label="Shapiro-Wilk normality test",
        input_mode=InputMode.ONE,
        description="Tests whether a sample was drawn from a normally distributed population.",
        assumptions="Observations are independent. Best for small-to-moderate sample sizes.",
        explanation=(
            "Checks whether one column of data plausibly comes from a normal (bell-shaped) distribution. This is "
            "often done BEFORE choosing a test, since t-tests and ANOVA assume normality.\n\n"
            "Note the logic is reversed here: the null hypothesis is that the data IS normal.\n"
            "• p ≥ 0.05 → keep the normal assumption; a t-test/ANOVA is reasonable.\n"
            "• p < 0.05 → the data is likely not normal; prefer a nonparametric test (Mann-Whitney, Wilcoxon, "
            "Kruskal-Wallis, or Spearman)."
        ),
        formula=(
            "W = ( Σ aᵢ · x₍ᵢ₎ )² / Σ (xᵢ − x̄)²\n\n"
            "x₍ᵢ₎ = data sorted from smallest to largest\n"
            "aᵢ   = special weights from the normal distribution\n"
            "x̄    = sample mean\n"
            "W close to 1 means the data looks normal."
        ),
        example=(
            "Before running a t-test on reaction times, check whether they are normal.\n\n"
            "• p ≥ 0.05 → looks normal, the t-test is appropriate.\n"
            "• p < 0.05 → not normal, use Mann-Whitney instead."
        ),
    ),
}


@dataclass
class StatTestResult:
    """Result of a statistical test, ready to be shown as data."""

    test_type: StatTestType
    test_name: str
    source_columns: list[str]
    statistic: float
    p_value: float
    alpha: float
    # Ordered (metric, value) pairs shown as the results table.
    rows: list[tuple[str, Any]] = field(default_factory=list)
    conclusion: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def significant(self) -> bool:
        """Whether the result is significant at the chosen alpha level."""
        return self.p_value is not None and self.p_value < self.alpha

    def to_dataframe(self) -> pd.DataFrame:
        """Convert the result into a tidy Metric/Value table."""
        return pd.DataFrame(self.rows, columns=["Metric", "Value"])

    def result_name(self) -> str:
        """Generate a default name for the results dataset."""
        cols = ", ".join(self.source_columns)
        return f"{self.test_name} [{cols}]"
