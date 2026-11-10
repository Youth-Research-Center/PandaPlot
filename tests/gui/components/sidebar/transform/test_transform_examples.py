"""Tests for the transform examples module's expression validator."""

import pytest

from pandaplot.gui.components.sidebar.transform.transform_examples import validate_expression_safety


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("", "Function code cannot be empty"),
        ("   ", "Function code cannot be empty"),
        ("open('x')", "This formula uses an operation that is not allowed, such as importing modules or accessing files."),
        ("x +", "The formula has a typo, for example a missing bracket, quote or operator."),
    ],
)
def test_invalid_expressions_use_plain_messages(expression: str, expected: str) -> None:
    is_safe, message = validate_expression_safety(expression)

    assert is_safe is False
    assert message == expected
    assert "Syntax error" not in message
    assert "Potentially unsafe" not in message


def test_valid_expression_has_no_message() -> None:
    assert validate_expression_safety("x * 2") == (True, "")
