"""Tests for the UserFacingError marker."""

import pytest

from pandaplot.utils.errors import UserFacingError


def test_user_facing_error_is_a_value_error():
    assert issubclass(UserFacingError, ValueError)
    with pytest.raises(ValueError, match="Pick a column."):
        raise UserFacingError("Pick a column.")
