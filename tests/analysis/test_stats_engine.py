"""Tests for the statistical testing engine."""

import numpy as np
import pandas as pd
import pytest

from pandaplot.analysis import STAT_TESTS, InputMode, StatsEngine, StatTestType


@pytest.fixture
def rng():
    return np.random.default_rng(42)


def _cols(**series):
    return [pd.Series(v, name=k) for k, v in series.items()]


class TestStatsEngine:
    def test_one_sample_t_detects_difference(self, rng):
        sample = rng.normal(10, 1, 60)
        result = StatsEngine.run_test(StatTestType.ONE_SAMPLE_T, _cols(A=sample), popmean=5.0)
        assert result.p_value < 0.05
        assert result.significant
        assert not result.to_dataframe().empty

    def test_independent_t_welch(self, rng):
        a = rng.normal(10, 1, 50)
        b = rng.normal(13, 1, 50)
        result = StatsEngine.run_test(StatTestType.INDEPENDENT_T, _cols(A=a, B=b), equal_var=False)
        assert result.p_value < 0.05
        assert any("Welch" in str(v) for _, v in result.rows)

    def test_paired_t_uses_complete_pairs_only(self):
        # Differences between the complete pairs (index 0, 1, 4) vary
        # (-1.5, -1.0, -2.2) rather than being identical, so the paired
        # differences have real variance and scipy doesn't hit the
        # near-zero-variance catastrophic-cancellation edge case.
        a = pd.Series([1.0, 2.0, 3.0, np.nan, 5.0], name="A")
        b = pd.Series([2.5, 3.0, np.nan, 4.0, 7.2], name="B")
        result = StatsEngine.run_test(StatTestType.PAIRED_T, [a, b])
        # Only 3 rows have both values present.
        n_pairs = dict(result.rows)["N pairs"]
        assert n_pairs == 3

    def test_anova_across_three_groups(self, rng):
        result = StatsEngine.run_test(
            StatTestType.ONE_WAY_ANOVA,
            _cols(A=rng.normal(0, 1, 40), B=rng.normal(3, 1, 40), C=rng.normal(6, 1, 40)),
        )
        assert result.p_value < 0.05

    def test_pearson_correlation(self):
        x = np.arange(50, dtype=float)
        result = StatsEngine.run_test(StatTestType.PEARSON, _cols(X=x, Y=2 * x + 1))
        assert result.statistic == pytest.approx(1.0, abs=1e-9)

    def test_shapiro_conclusion_inverted(self, rng):
        # Clearly non-normal (uniform) data should reject normality.
        result = StatsEngine.run_test(StatTestType.SHAPIRO, _cols(A=rng.uniform(0, 1, 300)))
        assert "NOT normally distributed" in result.conclusion

    def test_requires_enough_data(self):
        with pytest.raises(ValueError):
            StatsEngine.run_test(StatTestType.ONE_SAMPLE_T, _cols(A=[1.0]))

    def test_every_registered_test_runs(self, rng):
        data = {c: rng.normal(i, 1, 30) for i, c in enumerate(["A", "B", "C"])}
        df = pd.DataFrame(data)
        for test_type, info in STAT_TESTS.items():
            n = {InputMode.ONE: 1, InputMode.TWO: 2, InputMode.MANY: 3}[info.input_mode]
            cols = [df[c] for c in list(df.columns)[:n]]
            result = StatsEngine.run_test(test_type, cols)
            assert result.test_type == test_type
            assert not result.to_dataframe().empty

    def test_undefined_p_value_reports_could_not_be_computed(self):
        # A constant column makes Pearson's r (and its p-value) undefined (NaN).
        x = np.arange(10, dtype=float)
        with pytest.warns(Warning):
            result = StatsEngine.run_test(StatTestType.PEARSON, _cols(X=x, Y=np.full(10, 3.0)))
        assert np.isnan(result.p_value)
        assert not result.significant
        assert "could not be computed" in result.conclusion
        assert "Fail to reject" not in result.conclusion
        assert dict(result.rows)["Conclusion"] == result.conclusion
