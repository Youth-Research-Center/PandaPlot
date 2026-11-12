# Step 1 — Tokens (approved)

Picks: **1bL / 1bD** cleaned current base · **1eL / 1eD** teal accent · **1hL / 1hD** radius 4 / 6 / 4 (inner 3) · **Default** density (26px controls).

## Apply
1. Replace `ThemeManager.get_design_tokens()` body with `design_tokens.get_design_tokens(theme, density)`.
2. Merge `build_stylesheet()` rules into `ThemeManager.build_stylesheet` (adds `:focus`, heights, disabled, chip/segment fixes).
3. Remove the Storybook-local contrast overrides in `color_contrast.py`; extend `test_color_contrast.py` to every pair below.
4. Add `tokens_story.py` to Storybook (swatches + live contrast table).

## Contrast pairs to test (all pass)
text/surface 4.5 · muted/surface 4.5 · on_accent/accent 4.5 · sel_text/sel_bg 4.5 · danger/surface 4.5 · border_control/surface 3.0 · focus/surface 3.0

## Known follow-ups
- Default series colour 3 (`#2B7A8C`) sits close to teal — nudge to `#2F6FB0` or similar in the chart palette.
- `SectionHeader` should read `type["section"]` instead of inline 10.5px.
- `Card` margins 9 → `space["lg"]` (12).

## Focus ring (all controls)
QSS has no `outline`. Add a `FocusRing` helper: in `paintEvent` of PButton / fields / combos, when `hasFocus()` via keyboard, draw a 2px `focus` rounded rect 1px outside the control (radius + 2). Reserve 3px via parent spacing so it never clips. Border colours stay unchanged on focus.
