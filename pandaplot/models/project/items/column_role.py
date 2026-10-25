"""Experimental roles assigned to dataset columns."""

from enum import StrEnum


class ColumnRole(StrEnum):
    """Role a dataset column plays in an experimental measurement."""

    CONTROLLED = "controlled"
    FIXED = "fixed"
    MEASURED = "measured"
