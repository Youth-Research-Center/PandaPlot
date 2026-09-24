"""Typed chart-level figure/axes styling for Chart.style. See chart_config.py
for why the dict-style shim (`_legacy`, get/__getitem__/__setitem__/update)
exists -- kept here for interface parity even though every current style key
is already a declared field, so an unmigrated call site keeps working
unmodified against a ChartStyle instance."""
from dataclasses import dataclass, field, fields
from typing import Any, ClassVar


@dataclass
class ChartStyle:
    figure_size: tuple = (10, 6)
    figure_background_color: str | None = "#ffffff"
    axes_background_color: str | None = "#ffffff"
    font_size: int = 12
    font_family: str = "Arial"
    dpi: int = 100

    _legacy: dict = field(default_factory=dict, repr=False, compare=False)

    _FIELD_NAMES: ClassVar[frozenset] = frozenset()

    def __post_init__(self) -> None:
        # JSON has no tuple type -- a figure_size loaded from a persisted
        # project's dict arrives as a list (both via `cls(**known)` in
        # from_dict and via direct construction). Normalize it here so the
        # declared `tuple` type actually holds for every ChartStyle
        # instance, not just freshly-constructed defaults.
        if isinstance(self.figure_size, list):
            self.figure_size = tuple(self.figure_size)

    def get(self, key: str, default: Any = None) -> Any:
        if key in ChartStyle._FIELD_NAMES:
            return getattr(self, key)
        return self._legacy.get(key, default)

    def __getitem__(self, key: str) -> Any:
        if key in ChartStyle._FIELD_NAMES:
            return getattr(self, key)
        return self._legacy[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key == "figure_size" and isinstance(value, list):
            value = tuple(value)
        if key in ChartStyle._FIELD_NAMES:
            setattr(self, key, value)
        else:
            self._legacy[key] = value

    def __contains__(self, key: str) -> bool:
        return key in ChartStyle._FIELD_NAMES or key in self._legacy

    def update(self, mapping: dict) -> None:
        for key, value in mapping.items():
            self[key] = value

    def to_dict(self) -> dict:
        data = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "_legacy"}
        data.update(self._legacy)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ChartStyle":
        known = {k: v for k, v in data.items() if k in cls._FIELD_NAMES}
        legacy = {k: v for k, v in data.items() if k not in cls._FIELD_NAMES}
        style = cls(**known)
        style._legacy = legacy
        return style


ChartStyle._FIELD_NAMES = frozenset(f.name for f in fields(ChartStyle) if f.name != "_legacy")
