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


class TestGetTransformationTemplates:
    def test_returns_categories_with_name_code_description(self):
        templates = expression_engine.get_transformation_templates()
        assert "Math Operations" in templates
        entry = templates["Math Operations"][0]
        assert set(entry.keys()) == {"name", "code", "description"}
