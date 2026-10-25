"""Which points of a line/scatter series get a value label (#337)."""
from enum import StrEnum


class ValueLabelSubset(StrEnum):
    ALL = "all"
    EXTREMES = "extremes"
    MIN = "min"
    MAX = "max"
    LOCAL_EXTREMES = "local_extremes"

    @classmethod
    def coerce(cls, value: object) -> "ValueLabelSubset":
        """Return the member for `value`, or ALL when it is not a valid mode.

        Args:
            value: A member or its string value, possibly from a hand-edited project file.

        Returns:
            The matching member; ALL for an unknown or non-string value.
        """
        try:
            return cls(value)
        except ValueError:
            return cls.ALL