"""How the leader line (arrow) of a line/scatter value label is drawn (#504).

The defaults reproduce the arrow as it was drawn before it could be styled: a
thin, solid, black, plain line.
"""
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

# A label's arrow is black unless told otherwise. An empty color means "match the label text color".
DEFAULT_VALUE_LABEL_ARROW_COLOR = "#000000"
DEFAULT_VALUE_LABEL_ARROW_WIDTH = 1.0


class _FallbackStrEnum(StrEnum):
    """A `StrEnum` whose `coerce` maps anything unknown to its first member."""

    @classmethod
    def coerce(cls, value: object) -> Self:
        """Return the member for `value`, or the first member when it is not valid.

        Args:
            value: A member or its string value, possibly from a hand-edited project file.

        Returns:
            The matching member; the first member for an unknown or non-string value.
        """
        try:
            return cls(value)
        except ValueError:
            return next(iter(cls))


class ValueLabelArrowStyle(_FallbackStrEnum):
    """The shape of a value label's leader line; LINE is the historical look."""

    LINE = "line"
    ARROW = "arrow"
    FILLED_ARROW = "filled_arrow"


class ValueLabelArrowLineStyle(_FallbackStrEnum):
    """How the leader line is stroked; SOLID is the historical look."""

    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


def coerce_arrow_width(value: object) -> float:
    """Return `value` as a usable arrow line width.

    Args:
        value: A width, possibly from a hand-edited project file.

    Returns:
        `value` as a float, or the default width when it is not a finite positive number.
    """
    if isinstance(value, (int, float)):
        try:
            width = float(value)
        except OverflowError:
            return DEFAULT_VALUE_LABEL_ARROW_WIDTH
        if math.isfinite(width) and width > 0:
            return width
    return DEFAULT_VALUE_LABEL_ARROW_WIDTH


@dataclass
class ValueLabelArrowFields:
    """Arrow styling fields shared by the series styles that draw value labels with a leader line (Line and Scatter).

    Only read while the style's `value_label_show_arrow` is on.
    """

    value_label_arrow_style: ValueLabelArrowStyle = ValueLabelArrowStyle.LINE
    # "" means the arrow takes the label's text color.
    value_label_arrow_color: str = DEFAULT_VALUE_LABEL_ARROW_COLOR
    value_label_arrow_width: float = DEFAULT_VALUE_LABEL_ARROW_WIDTH
    value_label_arrow_line_style: ValueLabelArrowLineStyle = ValueLabelArrowLineStyle.SOLID

    def __post_init__(self) -> None:
        """Replace invalid values (e.g. from a hand-edited project) with the defaults."""
        self.value_label_arrow_style = ValueLabelArrowStyle.coerce(self.value_label_arrow_style)
        if not isinstance(self.value_label_arrow_color, str):
            self.value_label_arrow_color = DEFAULT_VALUE_LABEL_ARROW_COLOR
        self.value_label_arrow_width = coerce_arrow_width(self.value_label_arrow_width)
        self.value_label_arrow_line_style = ValueLabelArrowLineStyle.coerce(self.value_label_arrow_line_style)
