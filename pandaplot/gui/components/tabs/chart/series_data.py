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

    def copy(self) -> "SeriesData":
        """Deep-copy every array-like field, so the result is safe to read
        on a different thread than whatever mutates the source DataFrame."""
        def _copy_field(value):
            return value.copy() if hasattr(value, "copy") else value
        return SeriesData(
            x_data=_copy_field(self.x_data),
            y_data=_copy_field(self.y_data),
            x_err=_copy_field(self.x_err),
            y_err=_copy_field(self.y_err),
            x_err_minus=_copy_field(self.x_err_minus),
            y_err_minus=_copy_field(self.y_err_minus),
            error=self.error,
            u_data=_copy_field(self.u_data),
            v_data=_copy_field(self.v_data),
            magnitude_data=_copy_field(self.magnitude_data),
            z_data=_copy_field(self.z_data),
            z_label=self.z_label,
        )
