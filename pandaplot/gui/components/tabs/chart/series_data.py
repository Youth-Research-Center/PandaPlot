"""The per-series resolved-data carrier chart_editor.py's resolve_series_data()
returns and every SeriesType render function (series_renderers/) consumes.

Lives in its own module (rather than inside chart_editor.py, where it
originated) so the series_renderers/ package can import it without a
circular dependency on chart_editor.py.
"""
from dataclasses import dataclass
from typing import Any


@dataclass
class SeriesData:
    x_data: Any
    y_data: Any
    x_err: Any | None
    y_err: Any | None
    x_err_minus: Any | None
    y_err_minus: Any | None
    error: str | None
    u_data: Any | None = None
    v_data: Any | None = None
    magnitude_data: Any | None = None
    z_data: Any | None = None
