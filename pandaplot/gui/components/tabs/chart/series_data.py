"""The per-series resolved-data carrier chart_editor.py's resolve_series_data()
returns and every SeriesType render function (series_renderers/) consumes.

Lives in its own module (rather than inside chart_editor.py, where it
originated) so the series_renderers/ package can import it without a
circular dependency on chart_editor.py.
"""
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SeriesData:
    x_data: Any
    y_data: Any
    x_err: Optional[Any]
    y_err: Optional[Any]
    x_err_minus: Optional[Any]
    y_err_minus: Optional[Any]
    error: Optional[str]
    u_data: Optional[Any] = None
    v_data: Optional[Any] = None
    magnitude_data: Optional[Any] = None
    z_data: Optional[Any] = None
    z_label: str = ""
