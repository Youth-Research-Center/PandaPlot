"""Real design tokens for test mocks, so a mock can never drift from what `ThemeManager` produces.

Use these instead of hand-written token dicts or hard-coded accent colours:

- `design_tokens(theme, accent=..., **overrides)`: a fresh copy of the full token dict.
- `surface_palette(theme, accent=...)`: the matching `get_surface_palette()` dict.
- `theme_manager_for(theme, accent=...)`: a real `ThemeManager` carrying that context, for code that calls it directly
  (`build_stylesheet`, `get_design_tokens`).

`DEFAULT_ACCENT` is the configured default accent, so these follow a change of default without test edits.
"""

from typing import Any

from pandaplot.models.state.config import AppearanceConfig, Theme
from pandaplot.services.theme.theme_manager import ThemeContext, ThemeManager

DEFAULT_ACCENT: str = AppearanceConfig().accent_color


def theme_manager_for(theme: Theme = Theme.LIGHT, *, accent: str = DEFAULT_ACCENT, interface_font_size: int = 10) -> ThemeManager:
    """Return a `ThemeManager` with the given context and no event bus, config or `QApplication`.

    It can build tokens and stylesheets but not apply them; use a real `AppContext` for that.
    """
    manager = ThemeManager.__new__(ThemeManager)
    manager._current = ThemeContext(theme=theme, accent=accent, interface_font_size=interface_font_size)
    return manager


def design_tokens(theme: Theme = Theme.LIGHT, *, accent: str = DEFAULT_ACCENT, **overrides: Any) -> dict[str, Any]:
    """Return a fresh copy of the real design tokens for `theme` and `accent`.

    Args:
        theme: Light or dark.
        accent: The accent colour the tokens derive from.
        **overrides: Token values to replace, for a test that needs one distinctive value. Only existing keys.

    Raises:
        KeyError: If an override names a token that does not exist.
    """
    tokens = theme_manager_for(theme, accent=accent).get_design_tokens()
    unknown = sorted(set(overrides) - set(tokens))
    if unknown:
        raise KeyError(f"Unknown design token(s): {', '.join(unknown)}")
    return {**tokens, **overrides}


def surface_palette(theme: Theme = Theme.LIGHT, *, accent: str = DEFAULT_ACCENT) -> dict[str, str]:
    """Return the real `get_surface_palette()` dict for `theme` and `accent`."""
    return theme_manager_for(theme, accent=accent).get_surface_palette()
