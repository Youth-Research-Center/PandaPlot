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
    # The Z component of a 3-D vector's arrow (Vector3D series only -- see
    # SeriesTypeSpec.needs_w_column); z_data above is that same series'
    # spatial Z coordinate, an unrelated field.
    w_data: Any | None = None
    # Per-point text labels from an optional label column (a pie's wedge
    # names -- see SeriesTypeSpec.needs_label_column). None when the type
    # has no label column or the series leaves it blank.
    label_data: Any | None = None
    # Display name of the color column for the default colorbar label, resolved
    # up front so rendering never needs a live project lookup.
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
            w_data=_copy_field(self.w_data),
            magnitude_data=_copy_field(self.magnitude_data),
            z_data=_copy_field(self.z_data),
            label_data=_copy_field(self.label_data),
            z_label=self.z_label,
        )
