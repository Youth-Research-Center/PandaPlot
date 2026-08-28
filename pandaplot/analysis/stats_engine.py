"""
Statistical testing engine.

Provides a thin, well-documented wrapper around ``scipy.stats`` for the most
frequently used hypothesis tests. Every test returns a :class:`StatTestResult`
so the guided UI can present output consistently and add it to the project as
data.
"""

import logging
from typing import List, Sequence

import numpy as np
import pandas as pd

from .stats_types import STAT_TESTS, StatTestResult, StatTestType

logger = logging.getLogger(__name__)


def _fmt(value: float, digits: int = 6) -> str:
    """Format a float compactly, guarding against NaN/inf."""
    if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        return "n/a"
    return f"{value:.{digits}g}"


def _fmt_p(p: float) -> str:
    """Format a p-value, using scientific notation for very small values."""
    if p is None or np.isnan(p):
        return "n/a"
    if p < 1e-4:
        return f"{p:.2e}"
    return f"{p:.6f}"


def _clean(series: pd.Series) -> np.ndarray:
    """Coerce a column to a clean 1-D float array, dropping NaNs."""
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    return values[~np.isnan(values)]


def _clean_pair(a: pd.Series, b: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Coerce two columns to aligned float arrays, dropping rows with any NaN."""
    frame = pd.DataFrame({"a": pd.to_numeric(a, errors="coerce"), "b": pd.to_numeric(b, errors="coerce")}).dropna()
    return frame["a"].to_numpy(dtype=float), frame["b"].to_numpy(dtype=float)


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's d effect size for two independent samples (pooled SD)."""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return float("nan")
    var1, var2 = np.var(a, ddof=1), np.var(b, ddof=1)
    pooled = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled == 0:
        return float("nan")
    return float((np.mean(a) - np.mean(b)) / pooled)


def _effect_label(magnitude: float) -> str:
    """Rough qualitative label for a |Cohen's d|-style effect size."""
    m = abs(magnitude)
    if np.isnan(m):
        return "unknown"
    if m < 0.2:
        return "negligible"
    if m < 0.5:
        return "small"
    if m < 0.8:
        return "medium"
    return "large"


def _corr_strength(r: float) -> str:
    """Qualitative label for a correlation coefficient magnitude."""
    m = abs(r)
    if np.isnan(m):
        return "unknown"
    if m < 0.1:
        return "negligible"
    if m < 0.3:
        return "weak"
    if m < 0.5:
        return "moderate"
    if m < 0.7:
        return "strong"
    return "very strong"


class StatsEngine:
    """Runs statistical hypothesis tests and returns structured results."""

    @staticmethod
    def run_test(
        test_type: StatTestType,
        columns: Sequence[pd.Series],
        alpha: float = 0.05,
        alternative: str = "two-sided",
        popmean: float = 0.0,
        *,
        equal_var: bool = True,
    ) -> StatTestResult:
        """
        Run the requested statistical test.

        Args:
            test_type: Which test to run.
            columns: Data columns (as pandas Series). The number required depends
                on the test's input mode (one, two, or many columns).
            alpha: Significance level for the plain-language conclusion.
            alternative: Alternative hypothesis ('two-sided', 'less', 'greater').
            popmean: Expected population mean for the one-sample t-test.
            equal_var: Assume equal variance for the independent t-test (Welch if False).

        Returns:
            A populated :class:`StatTestResult`.
        """
        dispatch = {
            StatTestType.ONE_SAMPLE_T: StatsEngine._one_sample_t,
            StatTestType.INDEPENDENT_T: StatsEngine._independent_t,
            StatTestType.PAIRED_T: StatsEngine._paired_t,
            StatTestType.MANN_WHITNEY: StatsEngine._mann_whitney,
            StatTestType.WILCOXON: StatsEngine._wilcoxon,
            StatTestType.ONE_WAY_ANOVA: StatsEngine._one_way_anova,
            StatTestType.KRUSKAL_WALLIS: StatsEngine._kruskal_wallis,
            StatTestType.PEARSON: StatsEngine._pearson,
            StatTestType.SPEARMAN: StatsEngine._spearman,
            StatTestType.SHAPIRO: StatsEngine._shapiro,
        }
        handler = dispatch.get(test_type)
        if handler is None:
            raise ValueError(f"Unsupported test type: {test_type}")

        return handler(
            columns,
            alpha=alpha,
            alternative=alternative,
            popmean=popmean,
            equal_var=equal_var,
        )

    # ------------------------------------------------------------------
    # Individual tests
    # ------------------------------------------------------------------

    @staticmethod
    def _one_sample_t(columns, *, alpha, alternative, popmean, equal_var) -> StatTestResult:
        from scipy import stats

        sample = _clean(columns[0])
        name = str(columns[0].name)
        StatsEngine._require(condition=len(sample) >= 2, requirement="at least 2 valid observations")

        res = stats.ttest_1samp(sample, popmean=popmean, alternative=alternative)
        stat, p = float(res.statistic), float(res.pvalue)
        dof = len(sample) - 1
        mean = float(np.mean(sample))
        d = (mean - popmean) / np.std(sample, ddof=1) if np.std(sample, ddof=1) > 0 else float("nan")

        rows = [
            ("Test", "One-sample t-test"),
            ("Column", name),
            ("H0", f"mean = {popmean}"),
            ("Alternative", alternative),
            ("N", len(sample)),
            ("Sample mean", _fmt(mean)),
            ("Population mean", _fmt(popmean)),
            ("t-statistic", _fmt(stat)),
            ("Degrees of freedom", dof),
            ("p-value", _fmt_p(p)),
            ("Cohen's d", _fmt(d)),
            ("Effect size", _effect_label(d)),
            ("Significance level", alpha),
        ]
        return StatsEngine._build(
            StatTestType.ONE_SAMPLE_T, "One-sample t-test", [name],
            statistic=stat, p_value=p, alpha=alpha, rows=rows,
            subject=f"the mean of '{name}' differs from {popmean}",
        )

    @staticmethod
    def _independent_t(columns, *, alpha, alternative, popmean, equal_var) -> StatTestResult:
        from scipy import stats

        a, b = _clean(columns[0]), _clean(columns[1])
        na, nb = str(columns[0].name), str(columns[1].name)
        StatsEngine._require(condition=len(a) >= 2 and len(b) >= 2, requirement="at least 2 valid observations per group")

        res = stats.ttest_ind(a, b, equal_var=equal_var, alternative=alternative)
        stat, p = float(res.statistic), float(res.pvalue)
        d = _cohens_d(a, b)
        method = "Student's t-test" if equal_var else "Welch's t-test"

        rows = [
            ("Test", f"Independent t-test ({method})"),
            ("Group A", na),
            ("Group B", nb),
            ("H0", "mean(A) = mean(B)"),
            ("Alternative", alternative),
            ("N (A)", len(a)),
            ("N (B)", len(b)),
            ("Mean (A)", _fmt(np.mean(a))),
            ("Mean (B)", _fmt(np.mean(b))),
            ("Equal variance assumed", equal_var),
            ("t-statistic", _fmt(stat)),
            ("p-value", _fmt_p(p)),
            ("Cohen's d", _fmt(d)),
            ("Effect size", _effect_label(d)),
            ("Significance level", alpha),
        ]
        return StatsEngine._build(
            StatTestType.INDEPENDENT_T, "Independent t-test", [na, nb],
            statistic=stat, p_value=p, alpha=alpha, rows=rows,
            subject=f"the means of '{na}' and '{nb}' differ",
        )

    @staticmethod
    def _paired_t(columns, *, alpha, alternative, popmean, equal_var) -> StatTestResult:
        from scipy import stats

        a, b = _clean_pair(columns[0], columns[1])
        na, nb = str(columns[0].name), str(columns[1].name)
        StatsEngine._require(condition=len(a) >= 2, requirement="at least 2 complete pairs")

        res = stats.ttest_rel(a, b, alternative=alternative)
        stat, p = float(res.statistic), float(res.pvalue)
        diff = a - b
        d = np.mean(diff) / np.std(diff, ddof=1) if np.std(diff, ddof=1) > 0 else float("nan")

        rows = [
            ("Test", "Paired t-test"),
            ("Column A", na),
            ("Column B", nb),
            ("H0", "mean difference = 0"),
            ("Alternative", alternative),
            ("N pairs", len(a)),
            ("Mean difference", _fmt(np.mean(diff))),
            ("t-statistic", _fmt(stat)),
            ("Degrees of freedom", len(a) - 1),
            ("p-value", _fmt_p(p)),
            ("Cohen's d", _fmt(d)),
            ("Effect size", _effect_label(d)),
            ("Significance level", alpha),
        ]
        return StatsEngine._build(
            StatTestType.PAIRED_T, "Paired t-test", [na, nb],
            statistic=stat, p_value=p, alpha=alpha, rows=rows,
            subject=f"the paired measurements '{na}' and '{nb}' differ",
        )

    @staticmethod
    def _mann_whitney(columns, *, alpha, alternative, popmean, equal_var) -> StatTestResult:
        from scipy import stats

        a, b = _clean(columns[0]), _clean(columns[1])
        na, nb = str(columns[0].name), str(columns[1].name)
        StatsEngine._require(condition=len(a) >= 1 and len(b) >= 1, requirement="at least 1 valid observation per group")

        res = stats.mannwhitneyu(a, b, alternative=alternative)
        stat, p = float(res.statistic), float(res.pvalue)
        # Rank-biserial correlation as effect size.
        rbc = 1 - (2 * stat) / (len(a) * len(b)) if len(a) and len(b) else float("nan")

        rows = [
            ("Test", "Mann-Whitney U test"),
            ("Group A", na),
            ("Group B", nb),
            ("H0", "distributions of A and B are equal"),
            ("Alternative", alternative),
            ("N (A)", len(a)),
            ("N (B)", len(b)),
            ("Median (A)", _fmt(np.median(a))),
            ("Median (B)", _fmt(np.median(b))),
            ("U-statistic", _fmt(stat)),
            ("p-value", _fmt_p(p)),
            ("Rank-biserial r", _fmt(rbc)),
            ("Significance level", alpha),
        ]
        return StatsEngine._build(
            StatTestType.MANN_WHITNEY, "Mann-Whitney U test", [na, nb],
            statistic=stat, p_value=p, alpha=alpha, rows=rows,
            subject=f"the distributions of '{na}' and '{nb}' differ",
        )

    @staticmethod
    def _wilcoxon(columns, *, alpha, alternative, popmean, equal_var) -> StatTestResult:
        from scipy import stats

        a, b = _clean_pair(columns[0], columns[1])
        na, nb = str(columns[0].name), str(columns[1].name)
        StatsEngine._require(condition=len(a) >= 1, requirement="at least 1 complete pair")

        res = stats.wilcoxon(a, b, alternative=alternative)
        stat, p = float(res.statistic), float(res.pvalue)

        rows = [
            ("Test", "Wilcoxon signed-rank test"),
            ("Column A", na),
            ("Column B", nb),
            ("H0", "median difference = 0"),
            ("Alternative", alternative),
            ("N pairs", len(a)),
            ("Median difference", _fmt(np.median(a - b))),
            ("W-statistic", _fmt(stat)),
            ("p-value", _fmt_p(p)),
            ("Significance level", alpha),
        ]
        return StatsEngine._build(
            StatTestType.WILCOXON, "Wilcoxon signed-rank test", [na, nb],
            statistic=stat, p_value=p, alpha=alpha, rows=rows,
            subject=f"the paired measurements '{na}' and '{nb}' differ",
        )

    @staticmethod
    def _one_way_anova(columns, *, alpha, alternative, popmean, equal_var) -> StatTestResult:
        from scipy import stats

        groups = [_clean(c) for c in columns]
        names = [str(c.name) for c in columns]
        StatsEngine._require(condition=len(groups) >= 2, requirement="at least 2 groups")
        StatsEngine._require(condition=all(len(g) >= 2 for g in groups), requirement="at least 2 valid observations per group")

        res = stats.f_oneway(*groups)
        stat, p = float(res.statistic), float(res.pvalue)

        # eta-squared effect size = SS_between / SS_total.
        grand = np.concatenate(groups)
        grand_mean = np.mean(grand)
        ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in groups)
        ss_total = np.sum((grand - grand_mean) ** 2)
        eta_sq = ss_between / ss_total if ss_total > 0 else float("nan")

        rows = [
            ("Test", "One-way ANOVA"),
            ("Groups", ", ".join(names)),
            ("H0", "all group means are equal"),
            ("Number of groups", len(groups)),
            ("Total N", len(grand)),
            ("F-statistic", _fmt(stat)),
            ("df between", len(groups) - 1),
            ("df within", len(grand) - len(groups)),
            ("p-value", _fmt_p(p)),
            ("Eta-squared", _fmt(eta_sq)),
            ("Significance level", alpha),
        ]
        return StatsEngine._build(
            StatTestType.ONE_WAY_ANOVA, "One-way ANOVA", names,
            statistic=stat, p_value=p, alpha=alpha, rows=rows,
            subject="at least one group mean differs from the others",
        )

    @staticmethod
    def _kruskal_wallis(columns, *, alpha, alternative, popmean, equal_var) -> StatTestResult:
        from scipy import stats

        groups = [_clean(c) for c in columns]
        names = [str(c.name) for c in columns]
        StatsEngine._require(condition=len(groups) >= 2, requirement="at least 2 groups")
        StatsEngine._require(condition=all(len(g) >= 1 for g in groups), requirement="at least 1 valid observation per group")

        res = stats.kruskal(*groups)
        stat, p = float(res.statistic), float(res.pvalue)

        rows = [
            ("Test", "Kruskal-Wallis H test"),
            ("Groups", ", ".join(names)),
            ("H0", "all groups have the same distribution"),
            ("Number of groups", len(groups)),
            ("Total N", sum(len(g) for g in groups)),
            ("H-statistic", _fmt(stat)),
            ("Degrees of freedom", len(groups) - 1),
            ("p-value", _fmt_p(p)),
            ("Significance level", alpha),
        ]
        return StatsEngine._build(
            StatTestType.KRUSKAL_WALLIS, "Kruskal-Wallis H test", names,
            statistic=stat, p_value=p, alpha=alpha, rows=rows,
            subject="at least one group distribution differs from the others",
        )

    @staticmethod
    def _pearson(columns, *, alpha, alternative, popmean, equal_var) -> StatTestResult:
        from scipy import stats

        a, b = _clean_pair(columns[0], columns[1])
        na, nb = str(columns[0].name), str(columns[1].name)
        StatsEngine._require(condition=len(a) >= 3, requirement="at least 3 complete pairs")

        res = stats.pearsonr(a, b, alternative=alternative)
        r, p = float(res.statistic), float(res.pvalue)

        rows = [
            ("Test", "Pearson correlation"),
            ("Variable X", na),
            ("Variable Y", nb),
            ("H0", "no linear correlation (r = 0)"),
            ("Alternative", alternative),
            ("N pairs", len(a)),
            ("Correlation r", _fmt(r)),
            ("R-squared", _fmt(r * r)),
            ("Strength", _corr_strength(r)),
            ("p-value", _fmt_p(p)),
            ("Significance level", alpha),
        ]
        return StatsEngine._build(
            StatTestType.PEARSON, "Pearson correlation", [na, nb],
            statistic=r, p_value=p, alpha=alpha, rows=rows,
            subject=f"'{na}' and '{nb}' are linearly correlated",
        )

    @staticmethod
    def _spearman(columns, *, alpha, alternative, popmean, equal_var) -> StatTestResult:
        from scipy import stats

        a, b = _clean_pair(columns[0], columns[1])
        na, nb = str(columns[0].name), str(columns[1].name)
        StatsEngine._require(condition=len(a) >= 3, requirement="at least 3 complete pairs")

        res = stats.spearmanr(a, b, alternative=alternative)
        rho, p = float(res.statistic), float(res.pvalue)

        rows = [
            ("Test", "Spearman rank correlation"),
            ("Variable X", na),
            ("Variable Y", nb),
            ("H0", "no monotonic correlation (rho = 0)"),
            ("Alternative", alternative),
            ("N pairs", len(a)),
            ("Correlation rho", _fmt(rho)),
            ("Strength", _corr_strength(rho)),
            ("p-value", _fmt_p(p)),
            ("Significance level", alpha),
        ]
        return StatsEngine._build(
            StatTestType.SPEARMAN, "Spearman rank correlation", [na, nb],
            statistic=rho, p_value=p, alpha=alpha, rows=rows,
            subject=f"'{na}' and '{nb}' are monotonically correlated",
        )

    @staticmethod
    def _shapiro(columns, *, alpha, alternative, popmean, equal_var) -> StatTestResult:
        from scipy import stats

        sample = _clean(columns[0])
        name = str(columns[0].name)
        StatsEngine._require(condition=len(sample) >= 3, requirement="at least 3 valid observations")

        res = stats.shapiro(sample)
        stat, p = float(res.statistic), float(res.pvalue)

        rows = [
            ("Test", "Shapiro-Wilk normality test"),
            ("Column", name),
            ("H0", "data is normally distributed"),
            ("N", len(sample)),
            ("W-statistic", _fmt(stat)),
            ("p-value", _fmt_p(p)),
            ("Significance level", alpha),
        ]
        # For normality the "significant" interpretation is inverted, so build a
        # custom conclusion rather than the generic reject/fail helper.
        if p < alpha:
            conclusion = (
                f"Reject H0 (p = {_fmt_p(p)} < {alpha}): the data in '{name}' is likely NOT normally distributed. "
                "Consider a nonparametric test."
            )
        else:
            conclusion = (
                f"Fail to reject H0 (p = {_fmt_p(p)} >= {alpha}): no evidence that '{name}' departs from normality."
            )
        result = StatsEngine._build(
            StatTestType.SHAPIRO, "Shapiro-Wilk normality test", [name],
            statistic=stat, p_value=p, alpha=alpha, rows=rows, subject="",
        )
        result.conclusion = conclusion
        result.rows.append(("Conclusion", conclusion))
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require(*, condition: bool, requirement: str) -> None:
        if not condition:
            raise ValueError(f"This test requires {requirement}.")

    @staticmethod
    def _build(
        test_type: StatTestType,
        test_name: str,
        source_columns: List[str],
        statistic: float,
        p_value: float,
        alpha: float,
        rows: list,
        subject: str,
    ) -> StatTestResult:
        """Assemble a StatTestResult and append a plain-language conclusion row."""
        result = StatTestResult(
            test_type=test_type,
            test_name=test_name,
            source_columns=source_columns,
            statistic=statistic,
            p_value=p_value,
            alpha=alpha,
            rows=list(rows),
            metadata={"info": STAT_TESTS[test_type].label},
        )
        if subject:
            if p_value < alpha:
                conclusion = f"Reject H0 (p = {_fmt_p(p_value)} < {alpha}): evidence that {subject}."
            else:
                conclusion = f"Fail to reject H0 (p = {_fmt_p(p_value)} >= {alpha}): no significant evidence that {subject}."
            result.conclusion = conclusion
            result.rows.append(("Conclusion", conclusion))
        return result
