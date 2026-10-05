"""Date/time parsing helpers shared by editors and pandas models."""

from typing import Any

import pandas as pd


def parse_timestamp_or_nat(value: Any) -> pd.Timestamp:
    """Parse a date/time value, returning NaT for blank or invalid input."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return pd.NaT
    try:
        return pd.Timestamp(value)
    except (ValueError, TypeError):
        return pd.NaT
