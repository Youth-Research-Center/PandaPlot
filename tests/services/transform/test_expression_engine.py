"""Tests for the shared transform-expression engine."""

import pandas as pd
import pytest

from pandaplot.services.transform import expression_engine


class TestValidateExpression:
    def test_empty_expression_is_invalid(self):
        is_valid, message = expression_engine.validate_expression("")
        assert is_valid is False
        assert "empty" in message.lower()

    def test_simple_expression_is_valid(self):
        is_valid, message = expression_engine.validate_expression("x * 2")
        assert is_valid is True
        assert message == ""

    def test_syntax_error_is_invalid(self):
        is_valid, message = expression_engine.validate_expression("x *")
        assert is_valid is False
        assert "syntax" in message.lower()

    @pytest.mark.parametrize("expression", [
        "__import__('os')",
        "open('f.txt')",
        "globals()",
        "exec('pass')",
    ])
    def test_dangerous_expression_is_invalid(self, expression):
        is_valid, _message = expression_engine.validate_expression(expression)
        assert is_valid is False


class TestEvaluateExpression:
    def test_evaluates_against_local_vars(self):
        x = pd.Series([1, 2, 3])
        result = expression_engine.evaluate_expression("x * 2", {"x": x})
        assert result.tolist() == [2, 4, 6]

    def test_has_access_to_numpy_and_pandas(self):
        x = pd.Series([1.0, 4.0, 9.0])
        result = expression_engine.evaluate_expression("np.sqrt(x)", {"x": x})
        assert result.tolist() == [1.0, 2.0, 3.0]

    def test_reuses_a_provided_safe_globals_dict(self):
        safe_globals = expression_engine.build_safe_globals()
        x = pd.Series([1, 2, 3])
        result = expression_engine.evaluate_expression("x + 1", {"x": x}, safe_globals)
        assert result.tolist() == [2, 3, 4]

    def test_raises_on_invalid_expression(self):
        with pytest.raises(NameError):
            expression_engine.evaluate_expression("undefined_name", {})

    def test_builtins_outside_the_safe_globals_are_not_reachable(self):
        """eval() injects the real __builtins__ into a globals dict that lacks
        the key, so omitting it is not enough -- ord() isn't in the safe
        globals and must not resolve."""
        with pytest.raises(NameError):
            expression_engine.evaluate_expression("ord('a')", {})

    def test_evaluating_does_not_mutate_the_callers_safe_globals(self):
        safe_globals = expression_engine.build_safe_globals()
        before = set(safe_globals)

        expression_engine.evaluate_expression("1 + 1", {}, safe_globals)

        assert set(safe_globals) == before

    def test_a_precompiled_expression_can_be_evaluated_repeatedly(self):
        code = expression_engine.compile_expression("x + 1")
        assert expression_engine.evaluate_expression(code, {"x": 1}) == 2
        assert expression_engine.evaluate_expression(code, {"x": 10}) == 11


class TestExpressionAllowlist:
    """The AST allowlist enforced at the engine boundary (#154).

    Formula expressions are persisted in project files and re-evaluated
    without the Transform panel's regex pre-check, so the engine itself must
    refuse anything outside the arithmetic / pandas / numpy dialect.
    """

    @pytest.mark.parametrize("expression", [
        "__import__('os').getcwd()",
        "x.__class__",
        "().__class__.__bases__[0].__subclasses__()",
        "x.__init__.__globals__",
        "_private",
        "'{0.__class__}'.format(x)",
        "'{0}'.format_map({})",
        "(c for c in [1]).gi_frame.f_back",
        "pd.io.common.os.getcwd()",
        "np.testing",
        "np.ctypeslib",
        "[np][0].testing",
        "(lambda m: m.io)(pd)",
        "np.random.mtrand",
        "np.random.mtrand.np.testing",
        "x.plot()",
        "x.to_frame().style",
        "x.values.ctypes",
        "pd.read_pickle('f.pkl')",
        "pd.read_csv('f.csv')",
        "np.load('f.npy')",
        "np.fromfile('f.bin')",
        "x.to_pickle('f.pkl')",
        "x.to_csv('f.csv')",
        "x.eval('1 + 1')",
        "(y := x)",
        "f'{x.__class__}'",
        "f'{x:{x.__class__}}'",
        "await x",
        "[1 for _x in ()]",
    ])
    def test_unsafe_expression_is_rejected_before_it_runs(self, expression):
        with pytest.raises(expression_engine.UnsafeExpressionError):
            expression_engine.evaluate_expression(expression, {"x": pd.Series([1])})

    def test_numpy_and_pandas_still_work_through_the_module_proxies(self):
        x = pd.Series([3.0, 4.0])
        evaluate = expression_engine.evaluate_expression

        assert evaluate("np.linalg.norm(x)", {"x": x}) == pytest.approx(5.0)
        assert len(evaluate("np.random.normal(0, 1, len(x))", {"x": x})) == 2
        assert evaluate("np.pi", {}) == pytest.approx(3.14159, rel=1e-5)
        assert evaluate("pd.Timestamp('2024-01-02').day", {}) == 2
        assert bool(evaluate("isna(np.nan)", {}))

    def test_blocked_names_are_hidden_from_dir_on_the_proxies(self):
        numpy_proxy = expression_engine.build_safe_globals()["np"]

        assert "sqrt" in dir(numpy_proxy)
        assert "load" not in dir(numpy_proxy)

    def test_the_rejection_reason_is_user_readable(self):
        with pytest.raises(expression_engine.UnsafeExpressionError, match="__class__"):
            expression_engine.compile_expression("x.__class__")

    def test_a_syntax_error_is_still_a_syntax_error(self):
        with pytest.raises(SyntaxError):
            expression_engine.compile_expression("x *")

    @pytest.mark.parametrize("expression", [
        "x * 2",
        "value if value > 0 else 0",
        "np.sqrt(x) + np.log(x)",
        "round(x, 2)",
        "(x - x.mean()) / x.std()",
        "x.rolling(3).mean()",
        "x.rank(pct=True) * 100",
        "x.str.split().str[0]",
        "x.str.extract(r'(\\d+)').astype(float)",
        "pd.to_datetime(x).dt.strftime('%Y-%m-%d')",
        "(pd.Timestamp.now() - pd.to_datetime(x)).dt.days",
        "pd.to_datetime(x) + pd.Timedelta(days=1)",
        "cols['a'] + cols['b']",
        "cols.iloc[:, 0] + cols.iloc[:, 1]",
        "cols.sum(axis=1)",
        "row['a'] / row['b'] if row['b'] != 0 else 0",
        "len([v for v in row if pd.notna(v)])",
        "x.apply(lambda v: v * 2)",
        "x.apply(lambda v: f'{v:.2f}')",
        "[0 for _ in x]",
        "'%.2f' % 3.14159",
        "np.random.normal(0, 1, len(x))",
        "np.where(x > 0, x, -x)",
        "math.sqrt(4)",
        "sorted([3, 1, 2])",
        "{'a': 1}['a']",
        "x[x > 1]",
        "not (x > 1).any()",
    ])
    def test_the_supported_dialect_is_accepted(self, expression):
        expression_engine.compile_expression(expression)

    def test_every_shipped_template_is_accepted(self):
        from pandaplot.gui.components.sidebar.transform.transform_examples import QUICK_FUNCTIONS

        templates = expression_engine.get_transformation_templates()
        codes = [entry["code"] for entries in templates.values() for entry in entries]
        codes += [entry["code"] for entries in QUICK_FUNCTIONS.values() for entry in entries]
        assert codes
        for code in codes:
            expression_engine.compile_expression(code)


class TestGetTransformationTemplates:
    def test_returns_categories_with_name_code_description(self):
        templates = expression_engine.get_transformation_templates()
        assert "Math Operations" in templates
        entry = templates["Math Operations"][0]
        assert set(entry.keys()) == {"name", "code", "description"}
