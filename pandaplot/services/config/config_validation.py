"""Extended configuration validation logic (Phase 1.4).

Separates richer cross-section & format validation concerns from the
lightweight structural validation implemented inside individual dataclasses.

Responsibilities:
    * Provide a single entry point `validate_config` that can both adjust
      invalid values and return a list of human-readable warning strings.
    * Keep *correction* logic minimal and predictable; we favour clamping
      and fallback-to-default instead of raising errors.

The function is intentionally idempotent (re-running should not create new
warnings or further mutate already-corrected fields).
"""
from __future__ import annotations

from typing import List
import re

from pandaplot.models.state.config import ApplicationConfig, AppearanceConfig

# Hard bounds / defaults (centralised here for consistency)
ACCENT_COLOR_FALLBACK = AppearanceConfig().accent_color  # '#3B82F6'
MIN_AUTO_SAVE_INTERVAL = 5
MAX_AUTO_SAVE_INTERVAL = 3600  # 1 hour
MAX_INTERFACE_FONT = 36
MAX_EDITOR_FONT = 48

_HEX_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def validate_config(cfg: ApplicationConfig) -> List[str]:
    """Validate & normalise the configuration in-place.

    Returns:
        List of warning messages describing corrections performed.
    """
    warnings: List[str] = []

    # Delegate to section-level validators first (ensures minima etc.)
    cfg.validate()

    # Accent color format
    accent = cfg.appearance.accent_color
    if not isinstance(accent, str) or not _HEX_COLOR_RE.match(accent):
        if accent != ACCENT_COLOR_FALLBACK:  # avoid duplicate correction
            warnings.append(
                f"appearance.accent_color invalid ('{accent}'), reset to {ACCENT_COLOR_FALLBACK}"
            )
        cfg.appearance.accent_color = ACCENT_COLOR_FALLBACK

    # Auto-save interval bounds (only clamp if enabled)
    if cfg.auto_save.enabled:
        if cfg.auto_save.interval_seconds < MIN_AUTO_SAVE_INTERVAL:
            warnings.append(
                f"auto_save.interval_seconds < {MIN_AUTO_SAVE_INTERVAL}; clamped"
            )
            cfg.auto_save.interval_seconds = MIN_AUTO_SAVE_INTERVAL
        elif cfg.auto_save.interval_seconds > MAX_AUTO_SAVE_INTERVAL:
            warnings.append(
                f"auto_save.interval_seconds > {MAX_AUTO_SAVE_INTERVAL}; clamped"
            )
            cfg.auto_save.interval_seconds = MAX_AUTO_SAVE_INTERVAL

    # Font upper bounds
    if cfg.appearance.interface_font_size > MAX_INTERFACE_FONT:
        warnings.append(
            f"appearance.interface_font_size > {MAX_INTERFACE_FONT}; clamped"
        )
        cfg.appearance.interface_font_size = MAX_INTERFACE_FONT
    if cfg.appearance.editor_font_size > MAX_EDITOR_FONT:
        warnings.append(
            f"appearance.editor_font_size > {MAX_EDITOR_FONT}; clamped"
        )
        cfg.appearance.editor_font_size = MAX_EDITOR_FONT

    return warnings


__all__ = ["validate_config"]
